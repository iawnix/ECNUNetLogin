# 常见问题排查

> [English](../troubleshooting.md) · 简体中文

任何失败的命令带上 `--debug` 都会把每次出站 URL 打到 stderr，
通常一眼就能看出是哪一步出问题。

## 错误对照

| 现象                                                                | 原因 / 处理                                                                                                                                            |
| ------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------ |
| `--host is required`（退出码 `2`）                                  | 命令行没传 host，且配置文件里也没有。要么传 `--host`，要么跑 `setup.sh install` / `auth_ecnu config init` 把配置写好。                                  |
| `acid not found in portal index page`（退出码 `4`）                 | 门户首页 HTML 里没有形如 `/index_<acid>.html` 的链接。在配置里写死 `acid`，或运行时传 `--acid`，跳过自动探测。                                          |
| `challenge token not found in response: ...`（退出码 `4`）          | `/cgi-bin/get_challenge` 返回了意料之外的内容。带 `--debug` 重跑看实际响应；门户可能换了实现。                                                          |
| `request failed for http://...: timed out`（退出码 `3`）            | 门户连不上。确认是否在校园网或对应 VPN 内；可以调大 `--timeout`。                                                                                       |
| `invalid host: '...'` / `unsupported URL scheme: '...'`（退出码 `2`）| `host` 参数解析失败，或用了 `http`/`https` 以外的 scheme。                                                                                              |
| `password is required for login`（退出码 `2`）                      | 登录需要密码。`--username` 配合 `--password` / `--password-stdin` / `--ask-password` 三选一。                                                          |
| 登录成功但 `check` 显示离线                                          | 门户偶尔会接受认证但接入控制器随后踢掉。建议用 `login --check-after --json`，读 `status.online`。                                                      |
| Rich 输出显示成乱码 `\x1b[...`                                       | 你的终端不支持 256 色。可以 `\| less -R` 或换 `--json` / `--quiet`。                                                                                    |
| 安装后 `command not found: auth_ecnu`                                | venv 装的：`source .venv/bin/activate` 或直接调 `.venv/bin/auth_ecnu`；pipx 装的：确认 `~/.local/bin` 在 `PATH` 里。                                    |
| `--in-json schema_version X not supported`                          | JSON 文件的 schema 版本比当前 auth_ecnu 新。升级 auth_ecnu 或者降级 JSON。                                                                              |
| `--in-json needs ... 'action' field in the JSON`                    | 顶层调用 `auth_ecnu --in-json file.json` 时 JSON 必须含 `"action"`；或者把子命令补到 CLI 上。                                                          |
| `method=pipx requested but 'pipx' is not installed`                 | 安装器拒绝静默回退到其他方式。装 pipx（`python3 -m pip install --user pipx && pipx ensurepath`）或改用 `--method=venv`。                                |

## 何时该报 bug

如果某次请求之前能跑通、现在突然 `portal_error`，多半是门户改了
什么 —— 拿你 `--debug` 日志对比一下能复现的旧日志。要改
`protocol.py` 之前请先读 [`docs/protocol.md`](../protocol.md)，
里面有协议格式与可复现示例。
