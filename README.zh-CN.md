# ECNUNetLogin

> [English](README.md) · 简体中文

`auth_ecnu` —— 一个面向华师大 / SRun 校园网认证的小型 Python 命令行工具。
构造签名后的登录 / 注销请求、提交到校园门户、查询在线状态。默认采用
偏 hacker 风格的 Rich 终端输出；提供 JSON 与 quiet 模式供脚本调用。

唯一运行时依赖：[`rich`](https://github.com/Textualize/rich)。
要求 Python ≥ 3.10。MIT 许可。

## 安装

```bash
./scripts/setup.sh install
```

交互式：选择 `pipx` / `venv` / `user` 三种安装方式之一，填写
host 和 ac_id，完成。安装器**绝不**询问账号密码。详情见
[docs/zh-CN/install.md](docs/zh-CN/install.md)：非交互式安装、
Windows 用法、前置条件、对应的卸载流程。

## 几个常用命令

```bash
auth_ecnu login  -u USER --ask-password               # 登录
auth_ecnu check                                       # 我在线吗？
auth_ecnu logout -u USER                              # 注销
auth_ecnu check --json                                # 给脚本用
auth_ecnu --in-json /etc/auth_ecnu/cron.json          # 从 JSON 文件读取参数
auth_ecnu config init                                 # 重新写一份配置
auth_ecnu input-template --action login > run.json    # 生成 JSON 模板
```

完整参考见 [docs/zh-CN/cli.md](docs/zh-CN/cli.md)。

## 文档

- [docs/zh-CN/install.md](docs/zh-CN/install.md) —— 安装方式、卸载、状态查询
- [docs/zh-CN/cli.md](docs/zh-CN/cli.md) —— 子命令与 flag 完整参考
- [docs/zh-CN/scripting.md](docs/zh-CN/scripting.md) —— JSON 输出 schema、`--in-json`、退出码、自动化套路
- [docs/zh-CN/config.md](docs/zh-CN/config.md) —— 配置文件格式与**不存凭证**铁律
- [docs/zh-CN/troubleshooting.md](docs/zh-CN/troubleshooting.md) —— 常见错误对照
- [docs/protocol.md](docs/protocol.md) —— SRun `srun_bx1` 协议规范（英文）

## 许可与变更日志

MIT，见 [LICENSE](LICENSE)。版本差异见 [CHANGELOG.md](CHANGELOG.md)。

## 安全与合规

本工具仅用于认证你**自己**的华师大账号。请勿用它冒用他人账号、
绕过门户策略、对门户进行压力测试。绝不要把账号密码、登录响应 /
预览 JSON、签名请求等敏感产物提交到任何版本控制系统。
