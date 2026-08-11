# Scripting auth_ecnu

> English · [简体中文](zh-CN/scripting.md)

This page covers the machine-facing surface: JSON output, run files,
exit codes, and the `--quiet` mode. The shape is stable across patch
versions and tracked by `schema_version` in every JSON document.

## Output modes

| Mode    | Flag             | stdout / stderr               | Use case                          |
| ------- | ---------------- | ----------------------------- | --------------------------------- |
| `rich`  | (default)        | hacker-style terminal text    | interactive use                   |
| `json`  | `--json` / `--output json` | one JSON document per call    | scripts, monitoring, alerting     |
| `quiet` | `-q` / `--output quiet`    | nothing                       | exit-code-driven automation       |

In `quiet` mode the network call still happens; only output is
suppressed. The exit code carries the result.

## JSON output envelope

Every non-exception result is a JSON object containing the requested
data plus a top-level `meta` block. Every operational error document
is an object with `error` and `meta`.

```json
"meta": {
  "tool": "auth_ecnu",
  "version": "0.7.0",
  "command": "check",
  "schema_version": 2
}
```

`schema_version` is the contract this document specifies. Consumer
scripts should branch on the integer; future schema-breaking changes
bump it.

Output documents and run-file inputs currently use schema version `2`.

### `check`

```json
{
  "ip": "198.51.100.10",
  "meta": { "command": "check", "schema_version": 2, "tool": "auth_ecnu", "version": "0.7.0" },
  "online": true,
  "raw": "alice,1,2,0,0,0,0,0,198.51.100.10,0",
  "username": "alice"
}
```

- `online` — `true` iff the portal accepted the session. Prefer this
  over scraping `error` from the auth response — see below.
- `username` / `ip` — parsed from `raw`; either may be empty.
- `raw` — the original portal record; kept for debugging.

### `login` / `logout`

Before submitting a non-preview request, both commands query the current
portal status. If the target state is already satisfied, no auth request
is submitted and the command emits the same status fields as `check`,
with `meta.command` set to `login` or `logout`:

```json
{
  "meta": { "command": "login", ... },
  "online": true,
  "username": "alice",
  "ip": "...",
  "raw": "..."
}
```

If a request is needed, the command emits the decoded JSONP response
plus `meta`; field names vary across SRun deployments (`error`,
`suc_msg`, sometimes more). It exits `0` only when that response has
`error == "ok"`. Run `auth_ecnu check --json` explicitly afterward when
the script must verify the resulting state.

### `--preview` (login/logout)

Prints the signed request without submitting it. Useful for inspection
and for offline reproduction tests.

```json
{
  "meta": { "command": "login", ... },
  "query": "action=login&ac_id=1&username=...",
  "request": {
    "ac_id": "1",
    "action": "login",
    "chksum": "0123456789abcdef0123456789abcdef01234567",
    "info": "{SRBX1}...",
    "password": "{MD5}...",
    "username": "USER"
  }
}
```

Preview JSON is sensitive — it contains the signed payload derived
from your password and the temporary challenge token. Do not commit it
or share it.

## Errors

In `json` mode, errors go to **stderr** (not stdout) and use this shape:

```json
{
  "error": {
    "code": "network_error",
    "message": "request failed for http://10.0.0.1/cgi-bin/get_challenge: timed out"
  },
  "meta": { "command": "login", "schema_version": 2, ... }
}
```

`error.code` is one of `usage_error`, `network_error`, `portal_error`
(or `error` for the generic base). Match on `code`, not `message`.

## Exit codes

| Code | Meaning                                                   |
| ---- | --------------------------------------------------------- |
| 0    | success                                                   |
| 1    | valid negative result: rejected login/logout or offline check |
| 2    | usage error: missing/invalid CLI input or bad config file |
| 3    | network error: portal unreachable, timeout, DNS, TLS      |
| 4    | portal error: portal reachable but response malformed     |

## <a name="run-files"></a>Run files

Pass run parameters from a JSON file instead of a long command line:

```bash
auth_ecnu run run.json
```

This is useful for cron jobs, dotfile bootstrap, and config-as-data
workflows. The JSON file chooses the action; the CLI only says "run
this task".

### Schema (`schema_version: 2`)

```json
{
  "schema_version": 2,
  "action": "login",
  "host": "172.20.20.11",
  "username": "alice",
  "password": "secret",
  "acid": 1,
  "ip": "",
  "campus_postfix": "",
  "token": null,
  "config": null,
  "timeout": 8.0,
  "output": "json",
  "preview": false,
  "debug": false,
  "ask_password": false,
  "password_stdin": false
}
```

- `action` — `login` / `logout` / `check`; required.
- Boolean keys must be JSON booleans: `true` enables, `false`/`null` omits.
- Empty strings and `null` for value keys are treated as "not set".
- Unknown keys are silently ignored for forward compatibility.

Generate a starting point with:

```bash
auth_ecnu input-template --action login > run.json
auth_ecnu input-template --action check > check.json
```

### Output override

The file's `"output"` field controls the output mode. For ad-hoc
runs, you can override only the output mode from the CLI:

```bash
auth_ecnu run run.json --json
auth_ecnu run run.json --quiet
```

Other runtime values come from the run file, then the normal config
file, then built-in defaults.

### Security

Putting `password` in a JSON file is **weaker** than `--ask-password`
or `--password-stdin` because the secret lives on disk. If you must
do it (cron jobs, etc.):

- `chmod 600 run.json`
- Store it outside any git working tree
- Consider whether your backup tool reads it
- Prefer reading the password from a secrets manager into stdin:
  `pass auth_ecnu/alice | auth_ecnu login -u alice --password-stdin`

## Examples

Pipe a status check into a monitoring system:

```bash
auth_ecnu check --host 172.20.20.11 --json | curl -X POST -H "Content-Type: application/json" -d @- $WEBHOOK_URL
```

Boolean health-check usable in scripts:

```bash
if auth_ecnu check --host 172.20.20.11 --quiet; then
  echo "online"
else
  case $? in
    2) echo "config error" ;;
    3) echo "network down" ;;
    *) echo "portal issue" ;;
  esac
fi
```

Reproducible login from a saved JSON file:

```bash
auth_ecnu run /etc/auth_ecnu/cron.json
```
