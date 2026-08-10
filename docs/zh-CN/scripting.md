# 脚本化使用 auth_ecnu

> [English](../scripting.md) · 简体中文

本页说明面向机器的接口：JSON 输出、run 文件、退出码、`--quiet` 模式。
所有输出都带 `schema_version`，跨补丁版本稳定。

## 输出模式

| 模式    | 触发方式                       | stdout / stderr            | 适用场景                |
| ------- | ------------------------------ | -------------------------- | ----------------------- |
| `rich`  | （默认）                       | hacker 风格终端文本         | 交互式使用              |
| `json`  | `--json` / `--output json`     | 每次调用输出一个 JSON 文档 | 脚本、监控、告警        |
| `quiet` | `-q` / `--output quiet`        | 无输出                     | 仅靠退出码的自动化      |

`quiet` 模式下网络请求仍然真实发起，只是不打印任何东西。结果通过
退出码传递。

## JSON 输出信封

每个未发生异常的结果都是一个 JSON 对象，包含数据 + 顶层 `meta`。
运行错误则包含 `error` + `meta`。

```json
"meta": {
  "tool": "auth_ecnu",
  "version": "0.6.1",
  "command": "check",
  "schema_version": 1
}
```

`schema_version` 是本文档承诺的契约，下游脚本应基于该整数做分支；
未来不兼容的 schema 变更会递增该号。

### `check`

```json
{
  "ip": "198.51.100.10",
  "meta": { "command": "check", "schema_version": 1, "tool": "auth_ecnu", "version": "0.6.1" },
  "online": true,
  "raw": "alice,1,2,0,0,0,0,0,198.51.100.10,0",
  "username": "alice"
}
```

- `online` —— 仅当门户认为会话有效时为 `true`。务必读这个字段，
  不要去抓认证响应里的 `error`，理由见下。
- `username` / `ip` —— 从 `raw` 中解析；可能为空。
- `raw` —— 门户原始记录，留作调试。

### `login` / `logout`

解码后的 JSONP 响应 + `meta`。字段名随 SRun 部署而异
（`error`、`suc_msg`、有时还多几个）。需要稳定的成功信号时，配
`--check-after`：

```bash
auth_ecnu login -u alice --ask-password --check-after --json
```

会返回：

```json
{
  "meta": { "command": "login", ... },
  "response": { "error": "ok", "suc_msg": "login_ok" },
  "status":   { "online": true, "username": "alice", "ip": "..." }
}
```

判断成功请基于 `status.online`，不要基于 `response.suc_msg`。

不带 `--check-after` 时，只有门户响应中的 `error == "ok"` 才返回
退出码 `0`。带 `--check-after` 时，以实际目标状态为准：登录后在线，
注销后离线。

### `--preview`（login / logout）

只打印签名后的请求，不真正提交。便于核对和离线复现。

```json
{
  "meta": { "command": "login", ... },
  "query": "action=login&ac_id=1&username=...",
  "request": {
    "ac_id": "1",
    "action": "login",
    "chksum": "0123456789abcdef0123456789abcdef01234567",
    "info": "{SRBX1}...",
    "password": "{MD5}...",
    "username": "USER"
  }
}
```

Preview JSON 是敏感数据 —— 包含基于密码与一次性挑战 token 派生
出的签名负载，**不要**提交或外发。

## 错误

JSON 模式下错误**写到 stderr**（不是 stdout），格式：

```json
{
  "error": {
    "code": "network_error",
    "message": "request failed for http://10.0.0.1/cgi-bin/get_challenge: timed out"
  },
  "meta": { "command": "login", "schema_version": 1, ... }
}
```

`error.code` 是 `usage_error` / `network_error` / `portal_error`
（或基类 `error`）之一。脚本请基于 `code` 而非 `message` 做匹配。

## 退出码

| 码 | 含义                                                  |
| -- | ----------------------------------------------------- |
| 0  | 成功                                                  |
| 1  | 有效的否定结果：认证被拒绝，或 `check` 检测到离线     |
| 2  | 用户错：CLI 输入有误，或配置文件有问题                |
| 3  | 网络错：门户不可达、超时、DNS、TLS                    |
| 4  | 门户错：门户能连上，但响应不符合预期                  |

## <a name="run-files"></a>Run 文件

从 JSON 文件读取运行参数，取代很长的一串 CLI 参数：

```bash
auth_ecnu run run.json
```

适合 cron、dotfile bootstrap、config-as-data 场景。JSON 文件决定
具体 action，CLI 只表达"运行这个任务"。

### Schema（`schema_version: 1`）

```json
{
  "schema_version": 1,
  "action": "login",
  "host": "172.20.20.11",
  "username": "alice",
  "password": "secret",
  "acid": 1,
  "ip": "",
  "campus_postfix": "",
  "token": null,
  "config": null,
  "timeout": 8.0,
  "output": "json",
  "preview": false,
  "check_after": true,
  "debug": false,
  "ask_password": false,
  "password_stdin": false
}
```

- `action` —— `login` / `logout` / `check`，必填。
- 布尔键必须是 JSON boolean：`true` 启用，`false` / `null` 忽略。
- 值字段的空串 / `null` 视为"未设置"。
- 未知键静默忽略（向前兼容）。

可以直接用 `input-template` 生成一份起点模板：

```bash
auth_ecnu input-template --action login > run.json
auth_ecnu input-template --action check > check.json
```

### 输出覆盖

文件里的 `"output"` 控制输出模式。临时运行时，可以只在 CLI 上覆盖
输出模式：

```bash
auth_ecnu run run.json --json
auth_ecnu run run.json --quiet
```

其他运行参数来自 run 文件，然后是普通配置文件，最后是内置默认值。

### 安全

把 `password` 放进 JSON 文件**弱于** `--ask-password` 或
`--password-stdin`，因为密钥落盘了。如果非这么做不可（比如
cron 任务），请：

- `chmod 600 run.json`
- 放在任何 git 工作树之外
- 留意你的备份工具会不会读到它
- 更好的做法：从密钥管理器读到 stdin：
  `pass auth_ecnu/alice | auth_ecnu login -u alice --password-stdin`

## 例子

把状态检查 push 到监控系统：

```bash
auth_ecnu check --host 172.20.20.11 --json | curl -X POST -H "Content-Type: application/json" -d @- $WEBHOOK_URL
```

shell 里的健康检查：

```bash
if auth_ecnu check --host 172.20.20.11 --quiet; then
  echo "online"
else
  case $? in
    2) echo "config error" ;;
    3) echo "network down" ;;
    *) echo "portal issue" ;;
  esac
fi
```

可复现的 JSON 登录：

```bash
auth_ecnu run /etc/auth_ecnu/cron.json
```
