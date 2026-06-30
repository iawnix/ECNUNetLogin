# Changelog

Notable changes per release. Schema follows [Keep a Changelog](https://keepachangelog.com/)
and the project uses [Semantic Versioning](https://semver.org/).

## [0.4.0] — 2026-06-30

### Added
- **`auth_ecnu config init / show / path`** subcommands. `init`
  interactively (or non-interactively with `--yes`) writes the
  auth-setting file without rerunning the installer. `show` prints
  the parsed settings (rich/json/quiet, no credentials). `path`
  prints the resolved config file path.
- **`auth_ecnu input-template --action ACTION`** prints a clean
  `--in-json` template document for the requested action — makes the
  `--in-json` workflow discoverable from the CLI.
- **Chinese documentation** under `docs/zh-CN/`, with a top-level
  `README.zh-CN.md` landing page. English docs link to their Chinese
  counterparts at the top.

## [0.3.0] — 2026-06-30

### Added
- **Unified installer / uninstaller**: `scripts/setup.sh install`,
  `uninstall`, `status` — one entry point, choice of `pipx` / `venv` /
  `user`. Aborts with a clear message if the chosen method's
  prerequisite is missing rather than silently falling back. Writes
  the chosen layout to `~/.config/auth_ecnu/install-state` so
  uninstall reverses exactly what install did.
- **Initial config is written at install time** (`mode 600`), not
  expected to exist by chance.
- **`--in-json FILE`** — supply run parameters from a JSON file
  (`schema_version: 1`). Two call styles:
  `auth_ecnu --in-json run.json` (dispatch via `action` in the JSON)
  and `auth_ecnu auth --in-json run.json` (subcommand fixed on the
  CLI). Precedence: CLI explicit > JSON > config > defaults.
- **Status panel subtitle** now shows `portal=<host>` instead of the
  jargon `rad_user_info`.
- **`docs/` directory** with topic-specific docs:
  `install.md`, `cli.md`, `scripting.md`, `config.md`,
  `troubleshooting.md`. README is now a ~50-line landing page.

### Changed
- **README** slimmed from ~400 lines to ~50; detailed material moved
  to `docs/`.

### Removed
- **Legacy `~/.auth-setting` fallback.** This path is no longer read
  at all; migrate to `~/.config/auth_ecnu/setting` (the installer
  helps).
- **`username` config key.** It is silently ignored if present.
  Credentials must never be in the config file. Pass `-u` at runtime
  or use `--in-json` with a file you control (`mode 600`).
- **`scripts/install.sh` and `scripts/uninstall.sh`** — replaced by
  the unified `scripts/setup.sh`.

## [0.2.0] — 2026-06-30

### Added
- **XDG/AppData config path**: default location is now
  `${XDG_CONFIG_HOME:-~/.config}/auth_ecnu/setting` (Linux/macOS) or
  `%APPDATA%\auth_ecnu\setting` (Windows). The legacy `~/.auth-setting`
  location is still read transparently as a fallback.
- **JSON envelope `meta` block** on every successful and error
  document: `{tool, version, command, schema_version}`. Downstream
  scripts should branch on `meta.schema_version` (`1` today).
- **Structured error envelope** in JSON mode:
  `{"error": {"code", "message"}, "meta": {...}}` to stderr.
- **Granular exit codes**: `0` success, `2` usage error, `3` network
  error, `4` portal error.
- **`status` command alias** for `check`.
- **`banner` subcommand** prints a hacker-style ASCII banner; JSON mode
  emits `{"banner": "..."}` for tool detection.
- **`--quiet` / `-q`**: silence stdout and stderr; convey result via
  exit code only.
- **`--version` / `-V`**: print the tool version.
- **`username` field in the config file**: drop `--username` from
  routine invocations.
- **Network spinner** in rich mode: a hacker-styled `>>> step…`
  indicator wraps each portal request.
- **`OnlineStatus.from_portal_body()`** classmethod and `ip` field on
  the dataclass.
- **MIT LICENSE** and this CHANGELOG.
- **`docs/protocol.md`** — normative spec of the SRun `srun_bx1` wire
  format, including a worked-example chksum/info pair you can diff
  against.

### Changed
- **UI redesigned for minimal hacker-terminal feel**: removed nested
  `Panel`/`Table` borders. Output is now single-section-per-block
  (`> TITLE · subtitle` followed by indented field rows). Palette
  extended to magenta (hashes), cyan (info), yellow (warnings).
- **Model validation hierarchy unified**: `SrunUrlProvider.from_host`
  raises `ValueError`; the CLI boundary translates it to `UsageError`.
  `client.py` and `protocol.py` raise `UsageError` / `NetworkError` /
  `PortalError` so error codes are stable across the wire.
- **Decode failures** in portal responses now display a red
  `[DECODE FAIL]` header instead of a generic field dump.
- **Cryptographic fields** (`chksum`, `info`, `password`) are
  highlighted in magenta. `info` is truncated in the preview table
  but reproduced in full in the query payload block.

### Removed
- Conda dependency: `environment.yml` and `scripts/install_conda_env.sh`
  are gone. Use `pipx`, the new `scripts/install.sh` (venv), or
  `make install`.
- Hidden `--no-rich` flag (was a redundant alias for `--json`).
- Duplicated IP-from-raw parsing in `render.py`.

### Fixed
- Direct `OnlineStatus(raw=...)` construction now derives `ip` from
  field 8 via `__post_init__`, instead of relying on the renderer.

## [0.1.0] — 2026-05-28

### Added
- Initial Python refactor of the ECNU `auth_client`.
- `login` / `auth` / `logout` / `check` subcommands.
- Rich rendering of portal responses and signed-request preview.
- JSON output (`--output json` / `--json`).
- Legacy `~/.auth-setting` config file support.
- Offline unit tests for protocol signing and parsing.
