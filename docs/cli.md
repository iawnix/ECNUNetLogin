# CLI reference

> English · [简体中文](zh-CN/cli.md)

## Subcommands

| Subcommand | Purpose                                                       |
| ---------- | ------------------------------------------------------------- |
| `login`    | Fetch a challenge token, sign the request, submit it          |
| `auth`     | Alias for `login`                                             |
| `logout`   | Same flow as `login`, with `action=logout`                    |
| `check`    | `GET /cgi-bin/rad_user_info` and print the parsed status      |
| `status`   | Alias for `check`                                             |
| `banner`   | Print the auth_ecnu ASCII banner (good for `--json` detection)|
| `config`   | Manage the auth-setting file: `config init`, `config show`, `config path` |
| `input-template` | Print a `--in-json` template (`--action login\|auth\|logout\|check\|status`) |

`auth_ecnu --version` / `-V` prints the tool version.

### Config subcommands

```bash
auth_ecnu config path                                 # print resolved path
auth_ecnu config show                                 # show current values
auth_ecnu config show --json                          # same as JSON
auth_ecnu config init                                 # interactive write
auth_ecnu config init --yes --host=10.0.0.1 --acid=1  # non-interactive
auth_ecnu config init --force                         # overwrite existing
```

`config init` prompts for each field with the existing value (if any)
as the default. It writes the file with `mode 600` and never asks
for credentials.

### Generating an `--in-json` template

```bash
auth_ecnu input-template --action login > run.json    # full template
auth_ecnu input-template --action check > check.json  # minimal template
```

Edit the file, then run:

```bash
auth_ecnu --in-json run.json
```

## Common flags

- `--config FILE` / `-c` — path to an auth-setting file. Defaults to
  `${XDG_CONFIG_HOME:-~/.config}/auth_ecnu/setting`. See
  [config.md](config.md) for the schema.
- `--host HOST` / `-H` — SRun portal host (e.g. `172.20.20.11`).
- `--timeout SECONDS` — per-request timeout (default 8).
- `--debug` / `-d` — print each outbound URL to stderr.

## Identity

- `--username USER` / `-u` — your portal account. **Required at runtime**;
  never stored in the config file.
- `--campus-postfix SFX` — appended to `--username` unless already
  present (some deployments need `@unit`).

## Password input (login)

Pick exactly one of:

- `--password PASS` / `-p` — risky in shared shells (visible to `ps`,
  shell history). Use one of the next two if at all possible.
- `--password-stdin` — read the password from stdin
  (`echo $PASS | auth_ecnu auth -u USER --password-stdin`).
- `--ask-password` — prompt interactively (recommended).

## Request shaping

- `--ip IP` — bind to a client IP; empty lets the portal infer.
- `--acid N` — portal `ac_id`; defaults to the config or auto-detect.
- `--preview` — print the signed request without submitting it. Useful
  for inspecting before going live.
- `--check-after` — query online status immediately after the auth
  call. Combined with `--json`, returns a single envelope with both
  the auth response and the status.

## Output

- `--output rich|json|quiet` — pick the rendering mode.
- `--json` — shortcut for `--output json`.
- `--quiet` / `-q` — shortcut for `--output quiet` (silence stdout
  and stderr; convey results via exit code only).

## JSON input

- `--in-json FILE` — supply run parameters from a JSON file. See
  [scripting.md](scripting.md#in-json) for the schema and precedence
  rules.

## Examples

```bash
# Interactive login, rich output
auth_ecnu auth -u alice --ask-password

# Check online status as JSON
auth_ecnu check --host 172.20.20.11 --json

# Logout silently and propagate result via exit code
auth_ecnu logout -u alice --quiet

# Inspect the signed request without submitting
auth_ecnu auth -u alice --ask-password --preview

# Login then immediately verify, all under one JSON document
auth_ecnu auth -u alice --ask-password --check-after --json

# Same login flow but from a JSON file
auth_ecnu --in-json ~/secure/auth.json
```
