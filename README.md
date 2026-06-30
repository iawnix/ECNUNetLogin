# ECNUNetLogin

> English · [简体中文](README.zh-CN.md)

`auth_ecnu` — a small Python CLI for ECNU/SRun campus network
authentication. Builds signed login/logout requests, submits them to
the portal, and checks online status. Rich hacker-styled output by
default; JSON and quiet modes for scripts.

Only runtime dependency: [`rich`](https://github.com/Textualize/rich).
Requires Python ≥ 3.10. MIT-licensed.

## Install

```bash
./scripts/setup.sh install
```

Interactive — pick `pipx` / `venv` / `user`, supply host and ac_id,
done. The installer never asks for credentials. See
[docs/install.md](docs/install.md) for non-interactive use, Windows,
prerequisites, and the matching uninstaller.

## A few commands

```bash
auth_ecnu login  -u USER --ask-password               # login
auth_ecnu check                                       # am I online?
auth_ecnu logout -u USER                              # log out
auth_ecnu check --json                                # for scripts
auth_ecnu --in-json /etc/auth_ecnu/cron.json          # from a JSON file
```

Full reference: [docs/cli.md](docs/cli.md).

## Documentation

- [docs/install.md](docs/install.md) — install methods, uninstall, status.
- [docs/cli.md](docs/cli.md) — every subcommand and flag, with examples.
- [docs/scripting.md](docs/scripting.md) — JSON output schema, `--in-json` input, exit codes, automation patterns.
- [docs/config.md](docs/config.md) — config file format and the **no-credentials** rule.
- [docs/troubleshooting.md](docs/troubleshooting.md) — error table by symptom.
- [docs/protocol.md](docs/protocol.md) — normative spec of the SRun `srun_bx1` wire format, with a worked example.

## License and changelog

MIT. See [LICENSE](LICENSE). Per-release diff in [CHANGELOG.md](CHANGELOG.md).

## Security & responsible use

This tool is intended for authenticating your **own** ECNU campus
account. Do not use it to impersonate other accounts, bypass portal
policy, or run load tests against the portal. Never commit
credentials, captured login/preview JSON, or signed-request artefacts.
