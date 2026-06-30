# ECNUNetLogin

ECNUNetLogin is a Python refactor of the existing ECNU `auth_client`.

It provides a small command-line tool and importable Python modules for ECNU/SRun
campus network authentication. The tool can build signed login/logout requests,
submit them to the campus portal, and check the current online status.

## Install

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

## Commands

Default output is human-friendly Rich rendering. With a config file, common
commands stay short:

```bash
auth_ecnu auth --username USER --ask-password
auth_ecnu check
auth_ecnu logout --username USER
```

For scripts and other programs, add `--json` or `--output json`:

```bash
auth_ecnu check --host HOST --json
auth_ecnu build --action logout --username USER --token TOKEN --acid 1 --json
```

Without a config file, pass the host explicitly:

```bash
auth_ecnu auth --host 172.20.20.11 --username USER --ask-password
auth_ecnu check --host 172.20.20.11 --json
```

The legacy command shape is also accepted:

```bash
auth_ecnu --username USER --password PASS auth
auth_ecnu --username USER check
```

Subcommands:

- `login`: fetch portal parameters, build the signed request, and submit login.
- `logout`: fetch portal parameters, build the signed request, and submit logout.
- `check`: query `/cgi-bin/rad_user_info`.
- `build`: build a signed request offline without contacting the portal.

Useful options:

- `--dry-run` on `login`/`logout` prints the request without submitting it.
- `--json` is a shortcut for `--output json`.
- `--output rich|json` switches between user-friendly rendering and machine-readable JSON.
- `--password-stdin` and `--ask-password` avoid putting the password directly in shell history.
- `--campus-postfix` appends an account suffix when needed.

## Config File

By default, ECNUNetLogin reads `~/.auth-setting` if it exists:

```text
campus_url=""
acid="1"
host="172.20.20.11"
campus_postfix=""
```

Use another file with `--config PATH`.

`acid` is the SRun `ac_id`: the access-controller or portal entry ID used in
signed login/logout requests. For the shown ECNU portal, it is `1`. In normal
host mode the tool can auto-detect it from the portal page, but keeping it in
the config file avoids an extra lookup and matches the old `auth_client`
setting format.

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
