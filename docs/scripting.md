# Scripting auth_ecnu

> English · [简体中文](zh-CN/scripting.md)

This page covers the machine-facing surface: JSON output, JSON input,
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

Every success document is a JSON object containing the requested data
plus a top-level `meta` block. Every error document is an object with
`error` and `meta`.

```json
"meta": {
  "tool": "auth_ecnu",
  "version": "0.3.0",
  "command": "check",
  "schema_version": 1
}
```

`schema_version` is the contract this document specifies. Consumer
scripts should branch on the integer; future schema-breaking changes
bump it.

### `check` / `status`

```json
{
  "ip": "198.51.100.10",
  "meta": { "command": "check", "schema_version": 1, "tool": "auth_ecnu", "version": "0.3.0" },
  "online": true,
  "raw": "alice,1,2,0,0,0,0,0,198.51.100.10,0",
  "username": "alice"
}
```

- `online` — `true` iff the portal accepted the session. Prefer this
  over scraping `error` from the auth response — see below.
- `username` / `ip` — parsed from `raw`; either may be empty.
- `raw` — the original portal record; kept for debugging.

### `login` / `auth` / `logout`

The decoded JSONP response, plus `meta`. Field names vary across SRun
deployments (`error`, `suc_msg`, sometimes more). Scripts that need a
stable success signal should use `--check-after`:

```bash
auth_ecnu auth -u alice --ask-password --check-after --json
```

That returns:

```json
{
  "meta": { "command": "auth", ... },
  "response": { "error": "ok", "suc_msg": "login_ok" },
  "status":   { "online": true, "username": "alice", "ip": "..." }
}
```

Branch on `status.online`, not on `response.suc_msg`.

### `--preview` (login/logout)

Prints the signed request without submitting it. Useful for inspection
and for offline reproduction tests.

```json
{
  "meta": { "command": "auth", ... },
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
  "meta": { "command": "auth", "schema_version": 1, ... }
}
```

`error.code` is one of `usage_error`, `network_error`, `portal_error`
(or `error` for the generic base). Match on `code`, not `message`.

## Exit codes

| Code | Meaning                                                   |
| ---- | --------------------------------------------------------- |
| 0    | success                                                   |
| 2    | usage error: missing/invalid CLI input or bad config file |
| 3    | network error: portal unreachable, timeout, DNS, TLS      |
| 4    | portal error: portal reachable but response malformed     |

## <a name="in-json"></a>`--in-json FILE`

Pass run parameters from a JSON file instead of CLI flags. Useful for
cron jobs, dotfile bootstrap, and config-as-data workflows.

### Schema (`schema_version: 1`)

```json
{
  "schema_version": 1,
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
  "check_after": true,
  "debug": false,
  "ask_password": false,
  "password_stdin": false
}
```

- `action` — `login` / `auth` / `logout` / `check` / `status` / `banner`.
  **Required** if you don't pass a subcommand on the CLI.
- Boolean keys behave like `--flag`: `true` enables, `false`/`null` omits.
- Empty strings and `null` for value keys are treated as "not set".
- Unknown keys are silently ignored for forward compatibility.

### Two call styles

```bash
# 1. Top-level: action comes from the JSON file.
auth_ecnu --in-json run.json

# 2. Subcommand on the CLI; JSON fills in the rest.
auth_ecnu auth --in-json run.json
```

### Precedence

CLI explicit flag  >  JSON file value  >  config file  >  built-in default.

That is, if your JSON has `"output": "rich"` but you pass `--quiet` on
the command line, the run is quiet.

### Security

Putting `password` in a JSON file is **weaker** than `--ask-password`
or `--password-stdin` because the secret lives on disk. If you must
do it (cron jobs, etc.):

- `chmod 600 run.json`
- Store it outside any git working tree
- Consider whether your backup tool reads it
- Prefer reading the password from a secrets manager into stdin:
  `pass auth_ecnu/alice | auth_ecnu auth -u alice --password-stdin`

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
auth_ecnu --in-json /etc/auth_ecnu/cron.json
```
