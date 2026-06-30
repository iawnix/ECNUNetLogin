# ECNUNetLogin

ECNUNetLogin is a Python refactor of the existing ECNU `auth_client`.

It provides a small command-line tool and importable Python modules for ECNU/SRun
campus network authentication. The tool can build signed login/logout requests,
submit them to the campus portal, and check the current online status.

## Install

The Python package works on Linux, macOS, and Windows.

### Linux/macOS

Create or update the conda environment and install the local package in editable mode:

```bash
./scripts/install_conda_env.sh
```

The installer creates the `auth-ecnu` conda environment by default. Override the
environment name with:

```bash
AUTH_ECNU_ENV=my-auth-env ./scripts/install_conda_env.sh
```

After installation:

```bash
conda activate auth-ecnu
auth_ecnu -h
```

### Windows

Use Anaconda Prompt or PowerShell with conda initialized:

```powershell
conda env create -n auth-ecnu --file environment.yml
conda activate auth-ecnu
python -m pip install -e .
auth_ecnu -h
```

If the `auth-ecnu` environment already exists:

```powershell
conda env update -n auth-ecnu --file environment.yml --prune
conda activate auth-ecnu
python -m pip install -e .
```

The Bash installer under `scripts/` is for Linux/macOS shells. On Windows, use
the commands above unless you are running Git Bash or WSL.

## Commands

Default output is human-friendly Rich rendering with terminal-style panels.
With a config file, common commands stay short:

```bash
auth_ecnu auth --username USER --ask-password
auth_ecnu check
auth_ecnu logout --username USER
```

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

Useful options:

- `--preview` on `auth`/`login`/`logout` prints the signed request without submitting it.
- `--json` is a shortcut for `--output json`.
- `--output rich|json` switches between user-friendly rendering and machine-readable JSON.
- `--password-stdin` and `--ask-password` avoid putting the password directly in shell history.
- `--campus-postfix` appends an account suffix when needed.

## JSON Output

JSON mode is for scripts, monitoring jobs, and other programs. It writes one
complete JSON document to stdout for each command invocation. The tool does not
read command arguments from a JSON file; use command-line options or the
`~/.auth-setting` config file for inputs.

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
  "online": true,
  "raw": "USER,1,2,0,0,0,0,0,198.51.100.10,0",
  "username": "USER"
}
```

Use `online`, `username`, and `ip` for normal automation. `raw` is the original
comma-separated portal response and is kept for debugging or advanced SRun
compatibility checks.

Save a login result and immediate status check:

```bash
auth_ecnu auth --username USER --ask-password --check-after --json > login-result.json
```

When `--check-after` is used with JSON mode, the output contains both the
decoded portal response and the follow-up status:

```json
{
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

Typical preview output:

```json
{
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

## Config File

By default, ECNUNetLogin reads `~/.auth-setting` if it exists:

```text
campus_url=""
acid="1"
host="172.20.20.11"
campus_postfix=""
```

Use another file with `--config PATH`.

On Windows, `~/.auth-setting` means the file in the current user's home
directory, for example `C:\Users\<User>\.auth-setting`.

`acid` is the SRun `ac_id`: the access-controller or portal entry ID used in
signed login/logout requests. For the shown ECNU portal, it is `1`. In normal
host mode the tool can auto-detect it from the portal page, but keeping it in
the config file avoids an extra lookup and matches the old `auth_client`
setting format.

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
PYTHONPATH=src python3 -m unittest tests/test_auth_ecnu.py
```

## Layout

- `src/auth_ecnu/protocol.py`: request signing and encoding.
- `src/auth_ecnu/client.py`: portal HTTP client.
- `src/auth_ecnu/cli.py`: command-line interface.
- `src/auth_ecnu/models.py`: typed request/status models.
- `tests/test_auth_ecnu.py`: offline tests.

## Security

Do not commit credentials, portal secrets, private tokens, or local runtime state.
Use `--ask-password` or `--password-stdin` for real login attempts.
