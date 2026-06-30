# Install / Uninstall

> English · [简体中文](zh-CN/install.md)

auth_ecnu ships a single installer script — `scripts/setup.sh` —
that handles all install methods, writes an initial config, and
records the chosen layout so uninstall can undo exactly what install
did.

## Quick start (interactive)

```bash
./scripts/setup.sh install
```

The installer asks for:

1. **Install method** — one of `pipx`, `venv`, `user`. If the chosen
   method's prerequisite is missing on this machine, the script tells
   you what to install and exits without doing anything.
2. **Config file path** — defaults to
   `${XDG_CONFIG_HOME:-~/.config}/auth_ecnu/setting`.
3. **Initial portal values** — `host`, `acid`, `campus_postfix`. The
   installer **never** prompts for a username or password; credentials
   are not stored in the config file (see [config.md](config.md)).

Confirm with `auth_ecnu --version`.

## Methods

| Method | Best for                              | Where it lands                                            |
| ------ | ------------------------------------- | --------------------------------------------------------- |
| `pipx` | end users who want a global CLI       | `~/.local/share/pipx/venvs/auth-ecnu/`                    |
| `venv` | development, repo-local installs      | `<repo>/.venv/` (configurable with `--install-path`)      |
| `user` | quick install without an extra tool   | `~/.local` via `pip install --user`                       |

## Non-interactive install

Useful for provisioning scripts and CI:

```bash
./scripts/setup.sh install \
  --method=pipx \
  --host=172.20.20.11 \
  --acid=1 \
  --yes
```

`--yes` requires `--method`. Any value you do not pass becomes the
empty string (or `acid=1`).

## Uninstall

```bash
./scripts/setup.sh uninstall          # remove the package only
./scripts/setup.sh uninstall --purge  # also remove config + state file
./scripts/setup.sh uninstall --yes    # skip confirmation prompts
```

The uninstaller reads the state file written at install time
(`~/.config/auth_ecnu/install-state`) and does the right thing for the
recorded method (pipx uninstall / rm -rf the venv / pip uninstall).

If you installed manually outside `setup.sh`, remove the package by
hand:

```bash
pipx uninstall auth-ecnu       # pipx install
rm -rf <your-venv>             # venv install
pip uninstall -y auth-ecnu     # pip --user install
```

## Status

```bash
./scripts/setup.sh status
```

Prints method, install path, config path, install time, and version.
Exits non-zero when no install is recorded.

## Make targets

```bash
make install     # ≡ ./scripts/setup.sh install
make uninstall   # ≡ ./scripts/setup.sh uninstall
make purge       # ≡ ./scripts/setup.sh uninstall --purge
make status      # ≡ ./scripts/setup.sh status
make dev         # pip install -e . into the current Python environment
make test        # run unit tests
make build       # build sdist + wheel
make clean       # remove build artefacts
```

## Windows

`setup.sh` is bash. On Windows, install via pipx directly:

```powershell
py -m pip install --user pipx
py -m pipx install C:\path\to\ECNUNetLogin
auth_ecnu --version
```

Then create the config file by hand at
`%APPDATA%\auth_ecnu\setting`:

```text
host="172.20.20.11"
acid="1"
campus_postfix=""
campus_url=""
```

## Prerequisites

- Python ≥ 3.10
- The chosen method's tool: `pipx`, `python3-venv`, or `pip`.

`setup.sh` checks Python plus the selected method's prerequisite before
touching anything, and exits with a clear message if a prerequisite is
missing.
