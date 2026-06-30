# Config file

> English · [简体中文](zh-CN/config.md)

The auth-setting file holds portal-side identifiers that rarely change
between invocations: host, ac_id, optional postfix, optional URL.

## Location

| Platform     | Default path                                            |
| ------------ | ------------------------------------------------------- |
| Linux/macOS  | `${XDG_CONFIG_HOME:-~/.config}/auth_ecnu/setting`       |
| Windows      | `%APPDATA%\auth_ecnu\setting`                           |

Override at runtime with `--config PATH` / `-c PATH`.

The installer writes this file for you (`scripts/setup.sh install`)
with `mode 600` and skeleton values you provide interactively.

## Schema

```text
host="172.20.20.11"
acid="1"
campus_postfix=""
campus_url=""
```

| Key              | Type   | Purpose                                                       |
| ---------------- | ------ | ------------------------------------------------------------- |
| `host`           | string | SRun portal hostname or `host:port`. No scheme.               |
| `acid`           | int    | Portal `ac_id`. ECNU's deployment uses `1`.                   |
| `campus_postfix` | string | Account suffix; appended to `--username` if not already there |
| `campus_url`     | string | Currently informational; carried for compatibility            |

- Lines starting with `#` are comments.
- Whitespace around `key=value` is trimmed.
- Values may be quoted with `"` or `'`; the quotes are stripped.
- Unknown keys are silently ignored, so existing files don't break
  when new schema versions add fields.

## What NOT to put in the config

**Never store credentials in this file.** That means:

- ✗ `username`
- ✗ `password`
- ✗ Any tokens or session IDs

`username` is silently ignored if it appears (so existing files don't
break), but it does not populate anything. `password` is never read
from a config file by `auth_ecnu`.

Pass these at runtime instead:

```bash
auth_ecnu login -u alice --ask-password           # interactive
echo "$PASS" | auth_ecnu login -u alice --password-stdin   # from env
auth_ecnu --in-json /run/keys/auth.json          # from a private file
```

See [scripting.md](scripting.md#in-json) for the JSON input file
format, including its own security caveats.

## Migration from `~/.auth-setting`

Earlier auth_client-style setups often used `~/.auth-setting`.
auth_ecnu **does not** read that path; it is not a fallback. Move your file:

```bash
mkdir -p ~/.config/auth_ecnu
mv ~/.auth-setting ~/.config/auth_ecnu/setting
chmod 600 ~/.config/auth_ecnu/setting
```

While you're at it, remove any `username=` line from the file — see
above for why.
