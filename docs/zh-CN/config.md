# 配置文件

> [English](../config.md) · 简体中文

auth-setting 配置文件用来保存"门户层、且不常变"的标识：host、
ac_id、可选 postfix、可选 URL。

## 位置

| 平台         | 默认路径                                                |
| ------------ | ------------------------------------------------------- |
| Linux/macOS  | `${XDG_CONFIG_HOME:-~/.config}/auth_ecnu/setting`       |
| Windows      | `%APPDATA%\auth_ecnu\setting`                           |

运行时可用 `--config PATH` / `-c PATH` 覆盖。

安装器（`scripts/setup.sh install`）会以 `mode 600` 替你写一份；
也可以随时用 `auth_ecnu config init` 重写或更新，不必重装。

## 文件格式

```text
host="172.20.20.11"
acid="1"
campus_postfix=""
campus_url=""
```

| 键               | 类型   | 含义                                                          |
| ---------------- | ------ | ------------------------------------------------------------- |
| `host`           | string | SRun 门户主机或 `host:port`，不要带 `http://`                 |
| `acid`           | int    | 门户 `ac_id`，华师大用 `1`                                    |
| `campus_postfix` | string | 账号后缀；`--username` 末尾未带它时会自动追加                 |
| `campus_url`     | string | 仅作信息字段，保留兼容                                        |

- `#` 开头是注释。
- `key=value` 两侧的空白会被去掉。
- 值可用 `"` 或 `'` 包裹，引号会被剥掉。
- 未知键**静默忽略**，所以老配置不会因新版本而崩。

## **绝不能**写进配置的内容

**永远不要把凭证存进这个文件**，包括：

- ✗ `username`（账号）
- ✗ `password`（密码）
- ✗ token / session ID 等等

`username` 如果出现在文件里会被静默忽略（不破坏老配置），但也
不会被读取使用。`password` 永远不会从配置文件读取。

正确的传凭证方式：

```bash
auth_ecnu auth -u alice --ask-password                    # 交互式
echo "$PASS" | auth_ecnu auth -u alice --password-stdin   # 从环境变量
auth_ecnu --in-json /run/keys/auth.json                   # 从私有 JSON 文件
```

JSON 输入文件本身也有安全注意事项，详见
[scripting.md](scripting.md#in-json)。

## 从 `~/.auth-setting` 迁移

早期 auth_client 风格配置常放在 `~/.auth-setting`。auth_ecnu
**不再读**这个路径，请手动迁移：

```bash
mkdir -p ~/.config/auth_ecnu
mv ~/.auth-setting ~/.config/auth_ecnu/setting
chmod 600 ~/.config/auth_ecnu/setting
```

迁移时顺便把 `username=` 那行删掉 —— 理由见上面。

或者直接：

```bash
auth_ecnu config init   # 交互式，从零重写一份
```
