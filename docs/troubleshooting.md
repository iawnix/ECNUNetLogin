# Troubleshooting

> English · [简体中文](zh-CN/troubleshooting.md)

Run any failing command with `--debug` to log each outbound URL to
stderr; that almost always pinpoints which step is misbehaving.

## Common errors

| Symptom                                                                | Cause / fix                                                                                                                                                  |
| ---------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| `--host is required` (exit `2`)                                        | No host on the command line and no config file. Pass `--host` or run `setup.sh install` so the config gets written.                                          |
| `acid not found in portal index page` (exit `4`)                       | The portal's index HTML did not contain the expected `/index_<acid>.html` link. Set `acid` in the config file or pass `--acid` to skip the auto-detect step. |
| `challenge token not found in response: ...` (exit `4`)                | `/cgi-bin/get_challenge` returned an unexpected payload. Re-run with `--debug` to dump the actual response; the portal may have been updated.                |
| `request failed for http://...: timed out` (exit `3`)                  | Portal unreachable. Check you are on the campus network or the right VPN; raise `--timeout`.                                                                 |
| `invalid host: '...'` / `unsupported URL scheme: '...'` (exit `2`)     | The `host` argument did not parse as a valid hostname or used a scheme other than `http`/`https`.                                                            |
| `password is required for login` (exit `2`)                            | Combine `--username` with one of `--password`, `--password-stdin`, or `--ask-password`.                                                                      |
| Login looks successful but `check` says offline                        | Portal sometimes accepts a login that the access controller then drops. Prefer `login --check-after --json` and read `status.online`.                        |
| Rich output looks like raw ANSI codes (`\x1b[...`)                     | Your terminal does not support 256-color. Pipe through `less -R`, or use `--json` / `--quiet` for non-interactive shells.                                    |
| `command not found: auth_ecnu` after install                           | If you installed via `venv`, activate it (`source .venv/bin/activate`) or call `.venv/bin/auth_ecnu` directly. If `pipx`, ensure `~/.local/bin` is on `PATH`. |
| `--in-json schema_version X not supported`                             | The input JSON's `schema_version` is newer than this build. Update auth_ecnu or downgrade the JSON.                                                          |
| `--in-json needs ... 'action' field in the JSON`                       | You called `auth_ecnu --in-json file.json` without a subcommand and the JSON also lacks an `action`. Add `"action": "login"` (etc) or pass a subcommand.     |
| `method=pipx requested but 'pipx' is not installed`                    | Installer refused to fall back to another method. Install pipx (`python3 -m pip install --user pipx && pipx ensurepath`) or rerun with `--method=venv`.      |

## When to file a bug

If a request used to work and now fails with `portal_error`, the
portal probably changed something — diff your `--debug` log against
the working case. If `protocol.py` needs to change, see
[`protocol.md`](protocol.md) for the wire format and the worked
example.
