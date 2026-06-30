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

```bash
auth_ecnu login --host HOST --username USER --ask-password
auth_ecnu logout --host HOST --username USER --check-after
auth_ecnu check --host HOST
auth_ecnu build --action login --username USER --password PASS --token TOKEN --ip 192.0.2.10 --acid 1
```

Subcommands:

- `login`: fetch portal parameters, build the signed request, and submit login.
- `logout`: fetch portal parameters, build the signed request, and submit logout.
- `check`: query `/cgi-bin/rad_user_info`.
- `build`: build a signed request offline without contacting the portal.

Useful options:

- `--dry-run` on `login`/`logout` prints the request without submitting it.
- `--format json|query|both` controls request output for `build` and dry runs.
- `--password-stdin` and `--ask-password` avoid putting the password directly in shell history.
- `--campus-postfix` appends an account suffix when needed.

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
