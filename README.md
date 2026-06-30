# ECNUNetLogin

ECNUNetLogin is a Python refactor of the existing ECNU `auth_client`.

It provides a small command-line tool and importable Python modules for
ECNU/SRun campus network authentication. The tool can build signed
login/logout requests, submit them to the campus portal, and check the
current online status. Output is human-friendly Rich rendering by
default and switches to a stable JSON envelope for scripts.

The only runtime dependency is [`rich`](https://github.com/Textualize/rich);
the package targets Python 3.10+.

## Install

ECNUNetLogin no longer requires conda. Pick the path that matches how
you use Python:

### pipx (recommended for end users)

```bash
pipx install /path/to/ECNUNetLogin
auth_ecnu --version
```

`pipx` keeps the CLI isolated in its own virtualenv and exposes
`auth_ecnu` globally. To upgrade, run `pipx reinstall auth-ecnu`. To
remove, `pipx uninstall auth-ecnu`.

### Project venv (recommended for development)

```bash
./scripts/install.sh
source .venv/bin/activate
auth_ecnu --version
```

Override the venv location or interpreter:

```bash
AUTH_ECNU_VENV=/opt/auth ./scripts/install.sh
AUTH_ECNU_PYTHON=python3.11 ./scripts/install.sh
```

### Make targets

```bash
make install     # creates .venv and installs auth_ecnu editable
make test        # offline unit tests
make uninstall   # remove .venv
make purge       # remove .venv and ~/.auth-setting
make version     # print the installed version
make help        # list every target
```

### Uninstall

```bash
./scripts/uninstall.sh           # remove the project .venv
./scripts/uninstall.sh --purge   # also remove ~/.auth-setting
```

If installed via pipx instead:

```bash
pipx uninstall auth-ecnu
```

### Windows

PowerShell/Command Prompt:

```powershell
py -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -e .
auth_ecnu --version
```

## Commands

Default output is human-friendly Rich rendering with terminal-style panels.
With a config file, common commands stay short:

```bash
auth_ecnu auth --username USER --ask-password
auth_ecnu check
auth_ecnu logout --username USER
```

Rich output uses a hacker-terminal palette: bright/dim green for normal
fields, magenta for cryptographic material (`chksum`, `info`, signed
hashes), red for offline status and errors, yellow for soft warnings,
and cyan for informational hints (`>>> resolving challenge…`). A
spinner shows during each network step in rich mode (auto-hidden on
non-tty streams and in JSON mode).

For scripts and other programs, add `--json` or `--output json`:

```bash
auth_ecnu check --host HOST --json
auth_ecnu auth --username USER --ask-password --json
```

Without a config file, pass the host explicitly:

```bash
auth_ecnu auth --host 172.20.20.11 --username USER --ask-password
auth_ecnu check --host 172.20.20.11 --json
```

To inspect the signed request without submitting login, use preview mode. It
may contact the portal to fetch the temporary challenge token, but it does not
submit the final login request:

```bash
auth_ecnu auth --username USER --ask-password --preview --json
```

Subcommands:

- `login`: fetch portal parameters, build the signed request, and submit login.
- `auth`: alias for `login`.
- `logout`: fetch portal parameters, build the signed request, and submit logout.
- `check`: query `/cgi-bin/rad_user_info`.
- `status`: alias for `check`.
- `banner`: print the hacker-style ASCII banner (supports `--json`).

Useful options:

- `--version` / `-V` prints the tool version.
- `--preview` on `auth`/`login`/`logout` prints the signed request without submitting it.
- `--json` is a shortcut for `--output json`.
- `--output rich|json` switches between user-friendly rendering and machine-readable JSON.
- `--password-stdin` and `--ask-password` avoid putting the password directly in shell history.
- `--campus-postfix` appends an account suffix when needed.

## JSON Output

JSON mode is for scripts, monitoring jobs, and other programs. Each
invocation writes exactly one JSON document. Success documents land on
stdout; errors land on stderr (see below).

Every JSON document carries a `meta` block so downstream scripts can
branch on a single, stable field:

```json
"meta": {
  "tool": "auth_ecnu",
  "version": "0.2.0",
  "command": "check",
  "schema_version": 1
}
```

`schema_version` is the contract this README documents. Future schema
changes will bump it; consumer scripts should refuse unknown versions
rather than silently misinterpret fields.

Save the current online status to a JSON file:

```bash
auth_ecnu check --json > status.json
```

Inspect it with Python or `jq`:

```bash
python -m json.tool status.json
jq -r '.online' status.json
jq -r '.username // ""' status.json
jq -r '.ip // ""' status.json
```

Typical `check --json` output:

```json
{
  "ip": "198.51.100.10",
  "meta": {
    "command": "check",
    "schema_version": 1,
    "tool": "auth_ecnu",
    "version": "0.2.0"
  },
  "online": true,
  "raw": "USER,1,2,0,0,0,0,0,198.51.100.10,0",
  "username": "USER"
}
```

Use `online`, `username`, and `ip` for normal automation. `raw` is the
original comma-separated portal response and is kept for debugging or
advanced SRun compatibility checks.

Save a login result and immediate status check:

```bash
auth_ecnu auth --username USER --ask-password --check-after --json > login-result.json
```

When `--check-after` is used with JSON mode, the output contains both the
decoded portal response and the follow-up status, plus the `meta` block:

```json
{
  "meta": {
    "command": "auth",
    "schema_version": 1,
    "tool": "auth_ecnu",
    "version": "0.2.0"
  },
  "response": {
    "error": "ok",
    "suc_msg": "login_ok"
  },
  "status": {
    "ip": "198.51.100.10",
    "online": true,
    "raw": "USER,1,2,0,0,0,0,0,198.51.100.10,0",
    "username": "USER"
  }
}
```

Portal response fields may differ between SRun deployments, so scripts should
prefer the `status.online` value when they need a stable login success check.

Preview mode can save the signed request without submitting it:

```bash
auth_ecnu auth --username USER --ask-password --preview --json > request-preview.json
```

Typical preview output (truncated):

```json
{
  "meta": {"command": "auth", "schema_version": 1, "tool": "auth_ecnu", "version": "0.2.0"},
  "query": "callback=...&action=login&username=USER&ac_id=1&...",
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

Treat preview JSON as sensitive. It contains signed request fields derived from
the password and temporary challenge token. Do not commit, publish, or share
`request-preview.json`, `login-result.json`, or any real output captured from a
login session.

### Errors and exit codes

When a command fails in JSON mode, the tool emits a structured envelope
to **stderr** (not stdout) and exits with a non-zero code:

```json
{
  "error": {
    "code": "network_error",
    "message": "request failed for http://10.0.0.1/cgi-bin/get_challenge: timed out"
  },
  "meta": {
    "command": "auth",
    "schema_version": 1,
    "tool": "auth_ecnu",
    "version": "0.2.0"
  }
}
```

Exit codes:

| Code | Meaning                                                   |
| ---- | --------------------------------------------------------- |
| 0    | success                                                   |
| 2    | usage error: missing/invalid CLI input or bad config file |
| 3    | network error: portal unreachable, timeout, DNS, TLS      |
| 4    | portal error: portal reachable but response malformed     |

`error.code` matches one of `usage_error`, `network_error`, `portal_error`.
Scripts should branch on these rather than parsing `error.message`.

## Config File

By default, ECNUNetLogin reads its config from an XDG/AppData location:

| Platform     | Default path                                            |
| ------------ | ------------------------------------------------------- |
| Linux / macOS | `${XDG_CONFIG_HOME:-~/.config}/auth_ecnu/setting`      |
| Windows      | `%APPDATA%\auth_ecnu\setting`                           |

The legacy `~/.auth-setting` file is still picked up automatically as
a fallback, so existing users do not need to migrate. To move it
manually:

```bash
mkdir -p ~/.config/auth_ecnu
mv ~/.auth-setting ~/.config/auth_ecnu/setting
```

The file format is the same as the original `auth_client`:

```text
campus_url=""
acid="1"
host="172.20.20.11"
campus_postfix=""
username=""
```

Use another file with `--config PATH`.

`acid` is the SRun `ac_id`: the access-controller or portal entry ID used in
signed login/logout requests. For the shown ECNU portal, it is `1`. In normal
host mode the tool can auto-detect it from the portal page, but keeping it in
the config file avoids an extra lookup and matches the old `auth_client`
setting format.

`username` is optional. When set, `auth`/`login`/`logout` can be invoked
without `--username` and will pick it up from the config file.

The SRun `token` is a temporary challenge returned by the portal's
`/cgi-bin/get_challenge` endpoint. Normal `auth`, `login`, and `logout`
commands fetch it automatically. Users do not need to provide or know the token.

## Development

Run without installation:

```bash
PYTHONPATH=src python3 -m auth_ecnu -h
```

Run tests:

```bash
make test
# or:
PYTHONPATH=src python3 -m unittest discover -s tests -v
```

Byte-compile to catch syntax errors quickly:

```bash
make lint
```

## Layout

- `src/auth_ecnu/protocol.py`: request signing and encoding (pure functions).
- `src/auth_ecnu/client.py`: portal HTTP client.
- `src/auth_ecnu/cli.py`: command-line interface.
- `src/auth_ecnu/models.py`: typed request/status models.
- `src/auth_ecnu/render.py`: Rich rendering + JSON envelope.
- `src/auth_ecnu/errors.py`: error hierarchy and exit-code mapping.
- `src/auth_ecnu/config.py`: legacy `auth-setting` parser.
- `src/auth_ecnu/constants.py`: SRun protocol constants and `JSON_SCHEMA_VERSION`.
- `tests/test_auth_ecnu.py`: offline unit tests.
- `scripts/install.sh`, `scripts/uninstall.sh`: venv-based install/uninstall.
- `Makefile`: convenience targets.

## Security & responsible use

- Do not commit credentials, portal secrets, private tokens, or local runtime state.
- Use `--ask-password` or `--password-stdin` for real login attempts so the
  password never enters shell history.
- This tool is intended for authenticating your **own** ECNU campus
  account. Do not use it to impersonate other accounts, bypass portal
  policy, or perform load testing against the portal.
