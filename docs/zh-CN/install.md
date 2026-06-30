# 安装与卸载

> [English](../install.md) · 简体中文

auth_ecnu 提供一个统一的安装脚本 —— `scripts/setup.sh` —— 它包揽
所有安装方式、写入初始配置文件、并把所选布局记录下来，以便卸载
时能精确还原。

## 一键安装（交互式）

```bash
./scripts/setup.sh install
```

安装器会问你三件事：

1. **安装方式**：从 `pipx` / `venv` / `user` 中三选一。如果所选
   方式所依赖的工具在本机不存在，脚本会**直接提示并退出**，不会
   静默退而求其次。
2. **配置文件路径**：默认
   `${XDG_CONFIG_HOME:-~/.config}/auth_ecnu/setting`。
3. **初始门户参数**：`host`、`acid`、`campus_postfix`。安装器
   **绝不**询问账号密码 —— 凭证不存进配置文件，详见
   [config.md](config.md)。

完成后用 `auth_ecnu --version` 验证。

## 三种安装方式

| 方式   | 适合人群                          | 文件落点                                                  |
| ------ | --------------------------------- | --------------------------------------------------------- |
| `pipx` | 普通用户，想要全局可用的命令      | `~/.local/share/pipx/venvs/auth-ecnu/`                    |
| `venv` | 开发者，仓库内 .venv               | `<repo>/.venv/`（可用 `--install-path` 覆盖）             |
| `user` | 不想额外装 pipx，又不想 venv 隔离 | `~/.local`（`pip install --user`）                        |

## 非交互式安装

适合 CI 与自动化配置：

```bash
./scripts/setup.sh install \
  --method=pipx \
  --host=172.20.20.11 \
  --acid=1 \
  --yes
```

`--yes` 模式必须显式指定 `--method`。未传的可选参数默认为空串
（`acid` 默认 1）。

## 卸载

```bash
./scripts/setup.sh uninstall          # 仅卸载包
./scripts/setup.sh uninstall --purge  # 同时删除配置文件与状态文件
./scripts/setup.sh uninstall --yes    # 跳过确认提示
```

卸载脚本读取安装时写下的状态文件
（`~/.config/auth_ecnu/install-state`），根据记录的方式精确还原：
pipx uninstall / 删 venv 目录 / pip uninstall。

如果你是绕过 `setup.sh` 手动装的，自行卸载即可：

```bash
pipx uninstall auth-ecnu       # 通过 pipx 装的
rm -rf <your-venv>             # venv 装的
pip uninstall -y auth-ecnu     # pip --user 装的
```

## 查看当前安装状态

```bash
./scripts/setup.sh status
```

打印安装方式、安装路径、配置路径、安装时间、版本号。若没装过则
非零退出。

## Make 简写

```bash
make install     # ≡ ./scripts/setup.sh install
make uninstall   # ≡ ./scripts/setup.sh uninstall
make purge       # ≡ ./scripts/setup.sh uninstall --purge
make status      # ≡ ./scripts/setup.sh status
make dev         # 在当前 Python 环境 pip install -e .
make test        # 跑单元测试
make build       # 打 sdist + wheel
make clean       # 清构建产物
```

## Windows

`setup.sh` 是 bash 脚本，Windows 直接走 pipx：

```powershell
py -m pip install --user pipx
py -m pipx install C:\path\to\ECNUNetLogin
auth_ecnu --version
```

然后手动写配置到 `%APPDATA%\auth_ecnu\setting`：

```text
host="172.20.20.11"
acid="1"
campus_postfix=""
campus_url=""
```

或者用 `auth_ecnu config init` 走交互式问答。

## 前置条件

- Python ≥ 3.10
- 所选安装方式对应的工具：`pipx`、`python3-venv`、或 `pip`。

`setup.sh` 在开始前会检查 Python 和所选安装方式的依赖，缺什么会清楚地
提示让你装上再来。
