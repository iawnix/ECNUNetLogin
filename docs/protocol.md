# SRun `srun_bx1` portal protocol

A working spec of the protocol this tool implements, written so that
the request signer can be maintained without reading the implementation
line by line. Where the wire format is ambiguous or SRun-specific, the
rule is called out explicitly.

This document is the normative description of what `auth_ecnu` accepts
and emits. The signing scheme advertises itself in the `enc_ver` JSON
field as `srun_bx1`, which is the protocol name used here.

## Endpoint surface

A single SRun portal exposes four URLs, all relative to a portal host
like `http://172.20.20.11`:

| URL                          | Method | Purpose                                              |
| ---------------------------- | ------ | ---------------------------------------------------- |
| `/`                          | GET    | Discover `ac_id` from the redirect target's filename |
| `/cgi-bin/get_challenge`     | GET    | Issue a per-session challenge token                  |
| `/cgi-bin/srun_portal`       | GET    | Submit a signed login or logout request              |
| `/cgi-bin/rad_user_info`     | GET    | Check current online status                          |

Notes:

- All four use **HTTP GET with query parameters**. There is no POST
  body anywhere in this protocol.
- The portal answers `get_challenge` and `srun_portal` as JSONP if a
  `callback=` parameter is present. This tool always sets
  `callback=C_a_l_l_b_a_c_k` so responses look like
  `C_a_l_l_b_a_c_k({"foo":"bar"})`. The literal callback name is part
  of the protocol — do not change it.
- `rad_user_info` answers in plain text (comma-separated record) and
  does **not** honour `callback`.

## High-level state machine

```
                       ┌─────────────────┐
   ┌──────────────────►│ fetch ac_id     │  (only if not in config)
   │                   │ GET /           │
   │                   └────────┬────────┘
   │                            ▼
   │                   ┌─────────────────┐
   │                   │ fetch token     │
   │                   │ GET /get_challenge
   │                   └────────┬────────┘
   │                            ▼
   │                   ┌─────────────────┐
   │                   │ build signed    │
   │                   │ request map     │   (pure CPU)
   │                   └────────┬────────┘
   │                            ▼
   │                   ┌─────────────────┐
   │                   │ submit request  │
   │                   │ GET /srun_portal│
   │                   └────────┬────────┘
   │                            ▼
   │                   ┌─────────────────┐
   └───────────────────│ verify (opt)    │
                       │ GET /rad_user_info
                       └─────────────────┘
```

`ac_id` is the access-controller / portal entry ID — for ECNU's
deployment it is the constant `1`. The tool can either auto-detect it
by scraping the index page (regex `/index_([0-9]+)\.html`) or read it
from the config file, which is faster and avoids one round-trip.

`token` is the challenge — a short opaque string the portal issues
per call to `get_challenge`. It is the keying material for the
encrypted `info` field and is interleaved into the checksum.

## Field reference

A submitted `srun_portal` request is a flat key/value map. Values are
always strings on the wire.

| Field          | Always present? | Example value          | Source                                                   |
| -------------- | --------------- | ---------------------- | -------------------------------------------------------- |
| `callback`     | yes             | `C_a_l_l_b_a_c_k`      | Constant                                                 |
| `action`       | yes             | `login` / `logout`     | Caller                                                   |
| `ac_id`        | yes             | `1`                    | Config / autodetect                                      |
| `n`            | yes             | `200`                  | Constant                                                 |
| `type`         | yes             | `1`                    | Constant                                                 |
| `double_stack` | yes             | `1`                    | Constant                                                 |
| `ip`           | yes             | `192.0.2.10` or empty  | Caller (empty = let portal infer)                        |
| `username`     | yes             | `alice`                | Caller                                                   |
| `info`         | yes             | `{SRBX1}…`             | Computed (see below)                                     |
| `password`     | **login only**  | `{MD5}5ebe22…`         | `{MD5}` + MD5 hex of plaintext                           |
| `chksum`       | yes             | `31788c4f…` (40 hex)   | Computed (see below)                                     |

Logout requests use the same map *minus* the `password` field. The
checksum composition also differs between login and logout — see
[Checksum](#checksum).

## `info` field

`info` carries an encrypted snapshot of the credential context.

### Step 1 — Build the `authInfo` JSON object

```text
{
  "acid":     "<ac_id as decimal string>",
  "enc_ver":  "srun_bx1",
  "ip":       "<ip>",
  "username": "<username>",
  "password": "<plaintext password>"     ← login only; absent for logout
}
```

Serialization rules:

- **JSON keys are sorted alphabetically.** The Python implementation
  uses `sort_keys=True`.
- **Compact separators.** No spaces between keys/values. Equivalent
  to Python's `separators=(",", ":")`.
- **Strings are written verbatim.** No HTML/JSON escaping of CJK or
  other non-ASCII bytes (`ensure_ascii=False`).
- All values are JSON strings even when they look numeric (`"1"`, not
  `1`).

### Step 2 — XEncode

XEncode is SRun's XXTEA variant. It takes a UTF-8 string and a key
string, returns a byte string.

Word layout:

- Encode `data` as little-endian `uint32` words. Append one extra word
  equal to the **original byte length** of `data`.
- Encode `key` the same way but **without** the length suffix.
- Pad `k` to at least 4 words by appending zero words.

Schedule:

```
v       = data_words_with_len
k       = key_words
n       = len(v) - 1
rounds  = 6 + 52 // len(v)
sum     = 0
z       = v[n]
delta   = 0x9E3779B9
```

For each of `rounds` iterations:

```
sum += delta                                          (uint32)
e    = (sum >> 2) & 3

for p in 0..n:
    y   = v[0]  if p == n else v[p + 1]
    idx = (p & 3) ^ e
    mx  = ((z >> 5) ^ (y << 2))
        + (((y >> 3) ^ (z << 4)) ^ (sum ^ y))
        + (k[idx] ^ z)
    v[p] = (v[p] + mx) & 0xFFFFFFFF
    z    = v[p]
```

All shifts and XORs are **unsigned 32-bit**. In Python that means
mask every intermediate left-shift with `0xFFFFFFFF`.

Decode the final `v` back to little-endian bytes **without** the
length suffix. The result has the same byte length as
`ceil(len(data) / 4) * 4` — i.e. it is zero-padded up to a 4-byte
boundary. (This padding is part of the wire format; SRun never strips
it before base64 encoding.)

### Step 3 — quirk base64 encode

Encode the XEncode output with SRun's custom 64-character alphabet
(*not* the RFC 4648 alphabet):

```
LVoJPiCN2R8G90yg+hmFHuacZ1OWMnrsSTXkYpUq/3dlbfKwv6xztjI7DeBE45QA
```

The encoding pipeline is otherwise identical to base64: read three
input bytes, write four characters. The pad character is `=`.

**Quirk**: this dialect does not decide padding by counting *input
bytes mod 3*. It decides per output character by comparing running bit
position against total input bit count:

```
emit_char if (input_block_index * 8 + j * 6) <= len(data) * 8 else '='
```

For inputs whose length is a multiple of 3 this is equivalent to the
standard rule, but for shorter trailing groups it yields the same
output as standard base64 with this alphabet. Preserve the formula
exactly to stay byte-compatible with the portal.

### Step 4 — Prefix

Prepend the literal string `{SRBX1}`. The final field value is:

```
info = "{SRBX1}" + quirk_base64(xencode(json(authInfo), token))
```

## `password` field

For login requests only. Format:

```
pwd_field = "{MD5}" + lower(hex(MD5(plaintext_password)))
```

Logout requests omit `password` entirely.

Be aware: the MD5 of the password is also interleaved into the login
`chksum`, so the password is effectively committed to twice — once
encrypted inside `info`, once hashed in `chksum`.

## Checksum

`chksum` is the lower-case hex SHA-1 of a concatenated string that
weaves the token between every field. The portal verifies it
server-side as a tamper / replay guard.

**Login** (`action="login"`):

```
chksum = sha1_hex(
    token + username +
    token + md5_hex(password) +
    token + ac_id +
    token + ip +
    token + n            (the literal "200")
    token + type         (the literal "1")
    token + info
)
```

**Logout** (`action="logout"`):

```
chksum = sha1_hex(
    token + username +
    token + ac_id +
    token + ip +
    token + n            (the literal "200")
    token + type         (the literal "1")
    token + info
)
```

Notes:

- The MD5 hex used here is the **bare** hex digest, *without* the
  `{MD5}` prefix that goes in the request's `password` field.
- `info` is the full value **with** the `{SRBX1}` prefix.
- All values are concatenated as UTF-8 text.

## Worked example

Inputs (these are the same values used by
`tests/test_auth_ecnu.py::test_build_request_login_contains_signed_fields`,
so you can paste them into a REPL and compare):

```text
username fixture: alice
password fixture: secret
token fixture: abcdefghijklmnop
ip fixture: 192.0.2.10
ac_id fixture: 1
action fixture: login
```

Computed intermediates:

```text
md5_hex(password) = 5ebe2294ecd0e0f08eab7690d2a6ee69

info_json = {"acid":"1","enc_ver":"srun_bx1","ip":"192.0.2.10","password":"secret","username":"alice"}

xencode(info_json, token) bytes (hex):
  7954a04f4b8dac2a85c30ca65171156bb20dd038d527e4685e8cf0d9dcae7468
  d1c7430df3429e03933f103b65c1fdffae828787d04d8cac1ddb0c197bb3bd56
  273520489c5eab9c42266a1eb0c11ceecfbae42b90a078f13d743a60a3ff936a

info = {SRBX1}rumSFtK0lodivvxUHcPuOE20tJkuRQh/c/zvInxKnCkh6t904t8rLe9APJfpvs7Al/8NT5V0k8vnIvv1rEy5uXMj2PXMcdKM+X1dNlJVNyEgKK+lY8VD4FjtyUokAe0d

chksum = 31788c4f2352942da2b506e9a1015569416f5744
```

Final request map (before adding `callback`):

```text
action       = login
ac_id        = 1
n            = 200
type         = 1
double_stack = 1
ip           = 192.0.2.10
username     = alice
info         = {SRBX1}rumSFtK0lodivvxUHcPuOE20tJkuRQh/c/zvInxKnCkh6t904t8rLe9APJfpvs7Al/8NT5V0k8vnIvv1rEy5uXMj2PXMcdKM+X1dNlJVNyEgKK+lY8VD4FjtyUokAe0d
password     = {MD5}5ebe2294ecd0e0f08eab7690d2a6ee69
chksum       = 31788c4f2352942da2b506e9a1015569416f5744
```

If your implementation produces the same `chksum` for these inputs,
the signing pipeline is correct end-to-end. If it produces the same
`info` but a different `chksum`, the bug is in the checksum field
order (see [Checksum](#checksum)). If `info` differs, isolate
XEncode vs quirk-base64 by running each step independently.

To reproduce inside this repo:

```bash
PYTHONPATH=src python3 - <<'PY'
from auth_ecnu.protocol import build_request_params
from auth_ecnu.models import AuthParams
password_value = "secret"
token_value = "abcdefghijklmnop"
r = build_request_params(AuthParams(
    username="alice", password=password_value, token=token_value,
    action="login", ip="192.0.2.10", acid=1,
))
print(r["chksum"], r["info"][:24], "…")
PY
```

## Challenge endpoint

`GET /cgi-bin/get_challenge?ip=<ip>&username=<username>&double_stack=1&callback=C_a_l_l_b_a_c_k`

Response is JSONP. Strip `C_a_l_l_b_a_c_k(…)` and parse the JSON
object inside. Use the `challenge` field; everything else is
informational. The token is short-lived; build the signed request
immediately and submit it without sleeping.

## Online status

`GET /cgi-bin/rad_user_info` returns plain text, *not* JSONP.

- If the body contains the literal substring `not_online_error`, the
  client is offline.
- Otherwise the body is a comma-separated record. The first field is
  the authenticated username; the **9th field (index 8)** is the
  bound IP address. Other fields are session counters and are not
  used here.

Example (online):

```
alice,1,2,0,0,0,0,0,198.51.100.10,0
```

This tool parses this in `OnlineStatus.from_portal_body()` and
exposes `online`, `username`, `ip`, and `raw` on the model.

## Portal error codes

The portal's JSON response uses an `error` field, which may be the
literal `ok` or one of ~100 SRun-defined codes like `E2553`
(password incorrect) or `E2620` (already online).

The portal may return many deployment-specific error codes. `auth_ecnu`
keeps them as returned instead of translating them, because localized
messages and code tables can vary between SRun installations.

Notes on consuming `error`:

- A successful `auth` response also includes `suc_msg=login_ok`. Some
  deployments add extra fields (`username`, `online_ip`, billing
  counters). Be defensive: only treat `error == "ok"` as definitive.
- The error codes are stable across SRun deployments but `suc_msg`
  is not. Scripts that need a reliable success signal should follow
  up with a `check`/`rad_user_info` call — `auth_ecnu auth
  --check-after --json` does this and returns
  `{"response": {...}, "status": {...}}` in one shot.

## Where in the code

| Concept                         | File                                      | Symbol                                |
| ------------------------------- | ----------------------------------------- | ------------------------------------- |
| URL builder                     | `src/auth_ecnu/models.py`                 | `SrunUrlProvider`                     |
| `ac_id` regex                   | `src/auth_ecnu/protocol.py`               | `find_acid`                           |
| JSONP unwrap                    | `src/auth_ecnu/protocol.py`               | `find_json`                           |
| Challenge params                | `src/auth_ecnu/protocol.py`               | `build_challenge_params`              |
| `authInfo` build + JSON         | `src/auth_ecnu/protocol.py`               | `build_request_params` (line ~160)    |
| XEncode                         | `src/auth_ecnu/protocol.py`               | `xencode`                             |
| Quirk base64                    | `src/auth_ecnu/protocol.py`               | `quirk_base64_encode`                 |
| Custom alphabet, prefixes       | `src/auth_ecnu/constants.py`              | `CUSTOM_B64_ALPHABET`, `INFO_PREFIX`  |
| SHA-1                           | `src/auth_ecnu/protocol.py`               | `sha1sum`                             |
| `OnlineStatus` parse            | `src/auth_ecnu/models.py`                 | `OnlineStatus.from_portal_body`       |
| HTTP boundary                   | `src/auth_ecnu/client.py`                 | `SrunClient`, `get_text`              |

## Versioning

This document tracks the `srun_bx1` variant the ECNU portal speaks
today. If a future SRun release changes the alphabet, the `enc_ver`
string, the XEncode constants, or the chksum field order, treat it as a
new protocol version and add a sibling document rather than silently
rewriting this one.
