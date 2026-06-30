# 命令行参考

> [English](../cli.md) · 简体中文

## 子命令

| 子命令          | 作用                                                  |
| --------------- | ----------------------------------------------------- |
| `login`         | 拉取 challenge token、签名请求、提交登录              |
| `auth`          | `login` 的别名                                        |
| `logout`        | 同 `login` 流程，但 `action=logout`                   |
| `check`         | 调用 `/cgi-bin/rad_user_info`，打印解析后的状态       |
| `status`        | `check` 的别名                                        |
| `banner`        | 打印 ASCII banner（搭配 `--json` 可作工具探测）       |
| `config`        | 管理配置文件：`config init` / `config show` / `config path` |
| `input-template`| 输出 `--in-json` 模板（`--action login\|auth\|logout\|check\|status`） |

`auth_ecnu --version` / `-V` 打印版本号。

### config 子命令

```bash
auth_ecnu config path                                 # 打印解析后的配置文件路径
auth_ecnu config show                                 # 显示当前配置
auth_ecnu config show --json                          # 同上，JSON 格式
auth_ecnu config init                                 # 交互式写配置
auth_ecnu config init --yes --host=10.0.0.1 --acid=1  # 非交互式写
auth_ecnu config init --force                         # 覆盖已存在的文件
```

`config init` 会用现有文件里的值作为各字段的默认提示，写入时
使用 `mode 600`，且**绝不**询问账号密码。

### 生成 `--in-json` 模板

```bash
auth_ecnu input-template --action login > run.json    # 完整模板
auth_ecnu input-template --action check > check.json  # 精简模板
```

编辑文件后：

```bash
auth_ecnu --in-json run.json
```

## 通用 flag

- `--config FILE` / `-c` —— 配置文件路径。默认
  `${XDG_CONFIG_HOME:-~/.config}/auth_ecnu/setting`。详见
  [config.md](config.md)。
- `--host HOST` / `-H` —— SRun 门户主机（如 `172.20.20.11`）。
- `--timeout SECONDS` —— 单次请求超时（默认 8 秒）。
- `--debug` / `-d` —— 把每次出站请求 URL 打到 stderr。

## 身份

- `--username USER` / `-u` —— 你的校园账号。**必须运行时传入**，
  绝不存配置文件。
- `--campus-postfix SFX` —— 在 `--username` 后自动追加的后缀
  （比如 `@unit`），已存在则不重复追加。

## 密码输入（仅 login 用）

下面三种**任选其一**：

- `--password PASS` / `-p` —— 在共享环境危险，会被 `ps` / shell
  历史看到，能避免就避免。
- `--password-stdin` —— 从 stdin 读密码
  （`echo $PASS | auth_ecnu auth -u USER --password-stdin`）。
- `--ask-password` —— 交互式输入（推荐）。

## 请求塑形

- `--ip IP` —— 指定客户端 IP；留空让门户自动推断。
- `--acid N` —— 门户 `ac_id`；不传则按配置或自动探测。
- `--preview` —— 仅打印签名后的请求，不真正提交。调试用。
- `--check-after` —— 认证调用之后立即查询在线状态；与 `--json`
  合用时，会把认证响应与状态以单个 JSON 包返回。

## 输出模式

- `--output rich|json|quiet` —— 三选一。
- `--json` —— `--output json` 的简写。
- `--quiet` / `-q` —— `--output quiet` 的简写（抑制 stdout 与
  stderr，结果只通过退出码传递）。

## JSON 输入

- `--in-json FILE` —— 从 JSON 文件读取运行参数。schema 与优先级
  规则详见 [scripting.md](scripting.md#in-json)。

## 例子

```bash
# 交互式登录，rich 输出
auth_ecnu auth -u alice --ask-password

# 检查在线状态，JSON 输出
auth_ecnu check --host 172.20.20.11 --json

# 静默注销，结果靠退出码
auth_ecnu logout -u alice --quiet

# 只看签名后的请求，不提交
auth_ecnu auth -u alice --ask-password --preview

# 登录并立即验证，一个 JSON 文档全搞定
auth_ecnu auth -u alice --ask-password --check-after --json

# 同上但所有参数来自 JSON 文件
auth_ecnu --in-json ~/secure/auth.json
```
