"""Command-line interface for auth_ecnu."""

from __future__ import annotations

import argparse
import getpass
import json
import sys
from pathlib import Path
from typing import Any, Sequence

from . import __version__
from .client import SrunClient, decode_jsonp_or_json
from .config import AuthSetting, default_config_path, load_auth_setting, parse_setting_text
from .constants import DEFAULT_TIMEOUT
from .errors import AuthEcnuError, UsageError
from .models import OnlineStatus, SrunUrlProvider
from .render import (
    auth_response_payload,
    network_step,
    print_data,
    render_auth_response,
    render_error,
    render_request,
    render_status,
    status_payload,
)


CLI_DESCRIPTION = (
    "Built by iaw and Codex as a Python refactor of the existing ECNU auth_client "
    "for campus network login, logout, request signing, and online status checks."
)


def normalize_username(username: str | None, campus_postfix: str = "") -> str:
    if not username:
        raise UsageError("username is required")
    if campus_postfix and not username.endswith(campus_postfix):
        return f"{username}{campus_postfix}"
    return username


def resolve_password(args: argparse.Namespace, *, required: bool) -> str:
    password = getattr(args, "password", None) or ""
    if getattr(args, "password_stdin", False):
        stdin_value = sys.stdin.read().rstrip("\r\n")
        if password:
            raise UsageError("--password and --password-stdin cannot be used together")
        password = stdin_value
    if getattr(args, "ask_password", False):
        if password:
            raise UsageError("--password/--password-stdin and --ask-password cannot be used together")
        password = getpass.getpass("Password: ")
    if required and not password:
        raise UsageError(
            "password is required for login; use --password, --password-stdin, or --ask-password"
        )
    return password


def apply_config_defaults(args: argparse.Namespace) -> AuthSetting:
    setting = load_auth_setting(getattr(args, "config", None))
    if hasattr(args, "host") and not getattr(args, "host", None) and setting.host:
        args.host = setting.host
    if hasattr(args, "acid") and getattr(args, "acid", None) is None and setting.acid is not None:
        args.acid = setting.acid
    if hasattr(args, "campus_postfix") and not getattr(args, "campus_postfix", "") and setting.campus_postfix:
        args.campus_postfix = setting.campus_postfix
    return setting


def make_provider(args: argparse.Namespace) -> SrunUrlProvider:
    if not getattr(args, "host", None):
        config_hint = getattr(args, "config", None) or str(default_config_path())
        raise UsageError(
            f"--host is required; pass --host or set host in {config_hint}"
        )
    try:
        return SrunUrlProvider.from_host(args.host)
    except ValueError as exc:
        raise UsageError(str(exc)) from exc


def make_client(args: argparse.Namespace) -> SrunClient:
    return SrunClient(
        make_provider(args),
        timeout=getattr(args, "timeout", DEFAULT_TIMEOUT),
        debug=getattr(args, "debug", False) and getattr(args, "output", "rich") != "quiet",
    )


def _command_name(args: argparse.Namespace) -> str:
    return getattr(args, "command", "") or ""


def run_login(args: argparse.Namespace) -> int:
    apply_config_defaults(args)
    password = resolve_password(args, required=True)
    username = normalize_username(args.username, args.campus_postfix)
    client = make_client(args)
    command = _command_name(args)
    try:
        with network_step("resolving challenge & signing request", args.output):
            request = client.build_auth_request(
                username=username,
                password=password,
                action="login",
                ip=args.ip,
                acid=args.acid,
                token=args.token,
                include_callback=True,
            )
    except ValueError as exc:
        raise UsageError(str(exc)) from exc
    if args.preview:
        render_request("Signed Request", request, args.output, command=command)
        return 0
    with network_step("submitting login request", args.output):
        result = client.submit_auth(request)
    if args.output == "json" and args.check_after:
        with network_step("checking online status", args.output):
            status = client.check_online_status()
        print_data(
            {
                "response": auth_response_payload(result.body, decode_jsonp_or_json),
                "status": status_payload(status),
            },
            command,
        )
        return 0
    render_auth_response("Login Response", result.body, args.output, decode_jsonp_or_json, command=command)
    if args.check_after:
        print()
        with network_step("checking online status", args.output):
            status = client.check_online_status()
        render_status(status, args.output, command=command, host=getattr(args, "host", ""))
    return 0


def run_logout(args: argparse.Namespace) -> int:
    apply_config_defaults(args)
    username = normalize_username(args.username, args.campus_postfix)
    client = make_client(args)
    command = _command_name(args)
    try:
        with network_step("resolving challenge & signing request", args.output):
            request = client.build_auth_request(
                username=username,
                password="",
                action="logout",
                ip=args.ip,
                acid=args.acid,
                token=args.token,
                include_callback=True,
            )
    except ValueError as exc:
        raise UsageError(str(exc)) from exc
    if args.preview:
        render_request("Signed Request", request, args.output, command=command)
        return 0
    with network_step("submitting logout request", args.output):
        result = client.submit_auth(request)
    if args.output == "json" and args.check_after:
        with network_step("checking online status", args.output):
            status = client.check_online_status()
        print_data(
            {
                "response": auth_response_payload(result.body, decode_jsonp_or_json),
                "status": status_payload(status),
            },
            command,
        )
        return 0
    render_auth_response("Logout Response", result.body, args.output, decode_jsonp_or_json, command=command)
    if args.check_after:
        print()
        with network_step("checking online status", args.output):
            status = client.check_online_status()
        render_status(status, args.output, command=command, host=getattr(args, "host", ""))
    return 0


def run_check(args: argparse.Namespace) -> int:
    apply_config_defaults(args)
    client = make_client(args)
    with network_step("querying rad_user_info", args.output):
        status = client.check_online_status()
    render_status(status, args.output, command=_command_name(args), host=getattr(args, "host", ""))
    return 0


# ---------------------------------------------------------------------------
# config subcommand handlers
# ---------------------------------------------------------------------------


def _config_target(args: argparse.Namespace) -> Path:
    return Path(getattr(args, "config", None) or default_config_path()).expanduser()


def _prompt_default(label: str, default: str) -> str:
    suffix = f" [{default}]" if default else ""
    try:
        value = input(f"  {label}{suffix}: ")
    except EOFError:
        value = ""
    return value or default


def _format_setting(setting: AuthSetting) -> str:
    return (
        "# auth_ecnu setting file\n"
        "# WARNING: do not store passwords or other credentials here.\n"
        "# Pass -u/--ask-password at runtime, or use 'auth_ecnu run FILE'\n"
        "# with a JSON file you keep private (chmod 600).\n"
        "\n"
        f'host="{setting.host}"\n'
        f'acid="{setting.acid if setting.acid is not None else 1}"\n'
        f'campus_postfix="{setting.campus_postfix}"\n'
        f'campus_url="{setting.campus_url}"\n'
    )


def run_config_show(args: argparse.Namespace) -> int:
    setting = load_auth_setting(getattr(args, "config", None))
    path = _config_target(args)
    payload = {
        "path": str(path),
        "exists": path.exists(),
        "host": setting.host,
        "acid": setting.acid,
        "campus_postfix": setting.campus_postfix,
        "campus_url": setting.campus_url,
    }
    if args.output == "quiet":
        return 0
    if args.output == "json":
        print_data(payload, "config show")
        return 0
    # Rich text path: reuse the section renderer.
    from .render import _print_rows, _section, _value, _console
    console = _console()
    if console is None:
        for key, value in payload.items():
            print(f"{key}: {value}")
        return 0
    _section(console, "AUTH_ECNU CONFIG", subtitle=str(path))
    _print_rows(
        console,
        [
            ("EXISTS",         _value("yes" if payload["exists"] else "no")),
            ("HOST",           _value(setting.host)),
            ("AC_ID",          _value(setting.acid)),
            ("CAMPUS_POSTFIX", _value(setting.campus_postfix)),
            ("CAMPUS_URL",     _value(setting.campus_url)),
        ],
    )
    return 0


def run_config_path(args: argparse.Namespace) -> int:
    path = _config_target(args)
    if args.output == "quiet":
        return 0
    if args.output == "json":
        print_data({"path": str(path), "exists": path.exists()}, "config path")
        return 0
    print(path)
    return 0


def run_config_init(args: argparse.Namespace) -> int:
    path = _config_target(args)

    existing = AuthSetting()
    if path.exists():
        try:
            existing = parse_setting_text(path.read_text(encoding="utf-8"), source=str(path))
        except UsageError:
            pass  # malformed existing file — overwrite with prompts

    if args.yes:
        host = args.host if args.host is not None else existing.host
        acid = args.acid if args.acid is not None else (existing.acid if existing.acid is not None else 1)
        campus_postfix = args.campus_postfix if args.campus_postfix is not None else existing.campus_postfix
        campus_url = args.campus_url if args.campus_url is not None else existing.campus_url
    else:
        # Print a small heading so the user knows what's about to happen.
        print(f"  writing {path}")
        print("  (leave blank to keep the default shown in brackets)")
        host           = args.host           or _prompt_default("host", existing.host)
        acid_default   = str(existing.acid if existing.acid is not None else 1)
        acid_raw       = str(args.acid) if args.acid is not None else _prompt_default("ac_id", acid_default)
        try:
            acid = int(acid_raw)
        except ValueError:
            raise UsageError(f"ac_id must be an integer, got {acid_raw!r}")
        campus_postfix = args.campus_postfix if args.campus_postfix is not None else _prompt_default("campus_postfix", existing.campus_postfix)
        campus_url     = args.campus_url     if args.campus_url     is not None else _prompt_default("campus_url", existing.campus_url)

    if path.exists() and not args.force:
        if args.yes:
            raise UsageError(
                f"config already exists at {path}; pass --force to overwrite"
            )
        confirm = _prompt_default(f"overwrite existing {path}? (y/N)", "n")
        if confirm.lower() not in {"y", "yes"}:
            print("  aborted; existing config left unchanged.")
            return 0

    setting = AuthSetting(
        host=host,
        acid=acid,
        campus_postfix=campus_postfix,
        campus_url=campus_url,
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(_format_setting(setting), encoding="utf-8")
    try:
        path.chmod(0o600)
    except OSError:
        pass

    if args.output == "json":
        print_data({"path": str(path), "wrote": True}, "config init")
    elif args.output != "quiet":
        print(f"  wrote config to {path} (mode 600)")
    return 0


# ---------------------------------------------------------------------------
# run file and input-template subcommands
# ---------------------------------------------------------------------------


_INPUT_TEMPLATES: dict[str, dict[str, Any]] = {
    "login": {
        "schema_version": 1,
        "action": "login",
        "host": "",
        "username": "",
        "password": "",
        "acid": 1,
        "ip": "",
        "campus_postfix": "",
        "preview": False,
        "check_after": True,
        "output": "json",
        "timeout": 8.0,
    },
    "logout": {
        "schema_version": 1,
        "action": "logout",
        "host": "",
        "username": "",
        "acid": 1,
        "ip": "",
        "campus_postfix": "",
        "preview": False,
        "check_after": True,
        "output": "json",
        "timeout": 8.0,
    },
    "check": {
        "schema_version": 1,
        "action": "check",
        "host": "",
        "output": "json",
        "timeout": 8.0,
    },
}


_RUN_ACTIONS = ("login", "logout", "check")


def _load_run_file(path: str) -> dict[str, Any]:
    try:
        text = Path(path).expanduser().read_text(encoding="utf-8")
    except OSError as exc:
        raise UsageError(f"could not read run file {path!r}: {exc}") from exc
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise UsageError(f"run file {path!r} is not valid JSON: {exc}") from exc
    if not isinstance(data, dict):
        raise UsageError(f"run file {path!r} must be a JSON object")
    schema = data.get("schema_version")
    if schema is not None and schema != 1:
        raise UsageError(f"run file schema_version {schema!r} not supported (expected 1)")
    return data


def _json_text(data: dict[str, Any], key: str, default: str = "") -> str:
    value = data.get(key, default)
    if value is None:
        return default
    return str(value)


def _json_optional_text(data: dict[str, Any], key: str) -> str | None:
    value = data.get(key)
    if value is None or value == "":
        return None
    return str(value)


def _json_bool(data: dict[str, Any], key: str, default: bool = False) -> bool:
    value = data.get(key, default)
    if value is None or value == "":
        return default
    if isinstance(value, bool):
        return value
    raise UsageError(f"run file field {key!r} must be boolean")


def _json_int_or_none(data: dict[str, Any], key: str) -> int | None:
    value = data.get(key)
    if value is None or value == "":
        return None
    try:
        return int(value)
    except (TypeError, ValueError) as exc:
        raise UsageError(f"run file field {key!r} must be an integer") from exc


def _json_timeout(data: dict[str, Any]) -> float:
    value = data.get("timeout", DEFAULT_TIMEOUT)
    if value is None or value == "":
        return DEFAULT_TIMEOUT
    try:
        return float(value)
    except (TypeError, ValueError) as exc:
        raise UsageError("run file field 'timeout' must be a number") from exc


def _json_output(data: dict[str, Any], default: str | None = None) -> str | None:
    value = data.get("output", default)
    if value is None or value == "":
        return default
    value = str(value)
    if value not in {"rich", "json", "quiet"}:
        raise UsageError("run file field 'output' must be one of: rich, json, quiet")
    return value


def _namespace_from_run_file(data: dict[str, Any], *, output: str) -> argparse.Namespace:
    action = data.get("action")
    if not action:
        raise UsageError("run file needs an 'action' field")
    if action not in _RUN_ACTIONS:
        raise UsageError(f"run file 'action' must be one of {_RUN_ACTIONS}, got {action!r}")

    return argparse.Namespace(
        command=action,
        config=_json_optional_text(data, "config"),
        host=_json_optional_text(data, "host"),
        timeout=_json_timeout(data),
        debug=_json_bool(data, "debug"),
        output=output,
        username=_json_optional_text(data, "username"),
        campus_postfix=_json_text(data, "campus_postfix"),
        password=_json_text(data, "password"),
        password_stdin=_json_bool(data, "password_stdin"),
        ask_password=_json_bool(data, "ask_password"),
        token=_json_optional_text(data, "token"),
        ip=_json_text(data, "ip"),
        acid=_json_int_or_none(data, "acid"),
        preview=_json_bool(data, "preview"),
        check_after=_json_bool(data, "check_after"),
    )


def run_file(args: argparse.Namespace) -> int:
    data = _load_run_file(args.file)
    output = getattr(args, "output", None) or _json_output(data, default="rich") or "rich"
    args.output = output
    run_args = _namespace_from_run_file(data, output=output)
    args.command = run_args.command
    return {
        "login": run_login,
        "logout": run_logout,
        "check": run_check,
    }[run_args.command](run_args)


def run_input_template(args: argparse.Namespace) -> int:
    action = args.template_action
    template = _INPUT_TEMPLATES.get(action)
    if template is None:
        raise UsageError(
            f"no template for action={action!r}; choose from "
            f"{sorted(_INPUT_TEMPLATES)}"
        )
    # Raw print so the JSON is copy-pasteable straight into a run file.
    print(json.dumps(template, indent=2, sort_keys=True, ensure_ascii=False))
    return 0


def add_config_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--config",
        "-c",
        default=None,
        help=(
            "path to an auth-setting file (host, acid, campus_postfix, campus_url). "
            f"Defaults to {default_config_path()}. NEVER store credentials here."
        ),
    )


def add_common_network_args(parser: argparse.ArgumentParser) -> None:
    add_config_args(parser)
    parser.add_argument("--host", "-H", help="SRun portal host, e.g. 10.0.0.1")
    parser.add_argument("--timeout", type=float, default=DEFAULT_TIMEOUT, help="HTTP timeout in seconds")
    parser.add_argument("--debug", "-d", action="store_true", help="print HTTP requests to stderr")


def add_identity_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--username", "-u", required=False, help="account name; required for login/logout")
    parser.add_argument(
        "--campus-postfix",
        default="",
        help="append this suffix to --username unless it is already present",
    )


def add_password_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--password", "-p", default="", help="account password")
    parser.add_argument("--password-stdin", action="store_true", help="read password from stdin")
    parser.add_argument("--ask-password", action="store_true", help="prompt for password")


def add_output_args(parser: argparse.ArgumentParser, *, default: Any = "rich") -> None:
    parser.add_argument(
        "--output",
        choices=("rich", "json", "quiet"),
        default=default,
        help="rich (human), json (machine), or quiet (exit code only)",
    )
    parser.add_argument(
        "--json",
        dest="output",
        action="store_const",
        const="json",
        help="shortcut for --output json",
    )
    parser.add_argument(
        "--quiet",
        "-q",
        dest="output",
        action="store_const",
        const="quiet",
        help="suppress stdout and stderr; convey result via exit code only",
    )


def add_request_build_args(parser: argparse.ArgumentParser, *, default_action: str | None = None) -> None:
    if default_action is None:
        parser.add_argument("--action", choices=("login", "logout"), required=True)
    parser.add_argument("--token", help=argparse.SUPPRESS)
    parser.add_argument("--ip", default="", help="client IP; empty lets the portal infer it if supported")
    parser.add_argument("--acid", type=int, help="portal ac_id; defaults to config or auto-detect in host mode")


def add_auth_flow_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--preview", action="store_true", help="print the signed request without submitting it")
    parser.add_argument("--check-after", action="store_true", help="query online status after the request")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="auth_ecnu",
        description=CLI_DESCRIPTION,
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--version", "-V", action="version", version=f"auth_ecnu {__version__}")
    subparsers = parser.add_subparsers(dest="command", required=True)

    login = subparsers.add_parser("login", help="fetch token, build request, and submit login")
    add_common_network_args(login)
    add_identity_args(login)
    add_password_args(login)
    add_output_args(login)
    add_request_build_args(login, default_action="login")
    add_auth_flow_args(login)
    login.set_defaults(func=run_login)

    logout = subparsers.add_parser("logout", help="fetch token, build request, and submit logout")
    add_common_network_args(logout)
    add_identity_args(logout)
    add_output_args(logout)
    add_request_build_args(logout, default_action="logout")
    add_auth_flow_args(logout)
    logout.set_defaults(func=run_logout)

    check = subparsers.add_parser("check", help="query /cgi-bin/rad_user_info")
    add_common_network_args(check)
    add_output_args(check)
    check.set_defaults(func=run_check)

    run = subparsers.add_parser("run", help="run a JSON task file")
    run.add_argument("file", help="JSON task file with action=login/logout/check")
    add_output_args(run, default=argparse.SUPPRESS)
    run.set_defaults(func=run_file)

    # ── config ───────────────────────────────────────────────────────────
    config_cmd = subparsers.add_parser(
        "config",
        help="manage the auth-setting file (init / show / path)",
    )
    config_sub = config_cmd.add_subparsers(dest="config_command", required=True)

    cfg_init = config_sub.add_parser("init", help="write or update the setting file")
    add_config_args(cfg_init)
    add_output_args(cfg_init)
    cfg_init.add_argument("--host", default=None, help="portal host")
    cfg_init.add_argument("--acid", type=int, default=None, help="portal ac_id")
    cfg_init.add_argument("--campus-postfix", default=None, help="account suffix")
    cfg_init.add_argument("--campus-url", default=None, help="informational campus URL")
    cfg_init.add_argument("--yes", "-y", action="store_true",
                          help="non-interactive; use provided flags + existing values")
    cfg_init.add_argument("--force", "-f", action="store_true",
                          help="overwrite an existing file without prompting")
    cfg_init.set_defaults(func=run_config_init)

    cfg_show = config_sub.add_parser("show", help="print current config (no credentials)")
    add_config_args(cfg_show)
    add_output_args(cfg_show)
    cfg_show.set_defaults(func=run_config_show)

    cfg_path = config_sub.add_parser("path", help="print the resolved config file path")
    add_config_args(cfg_path)
    add_output_args(cfg_path)
    cfg_path.set_defaults(func=run_config_path)

    # ── input-template ───────────────────────────────────────────────────
    tmpl = subparsers.add_parser(
        "input-template",
        help="print a run-file JSON template for an action",
    )
    tmpl.add_argument(
        "--action",
        dest="template_action",
        choices=sorted(_INPUT_TEMPLATES),
        default="login",
        help="which action's template to print",
    )
    tmpl.set_defaults(func=run_input_template)

    return parser


def main(argv: Sequence[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    parser = build_parser()
    if not argv:
        parser.print_help()
        return 0

    try:
        args = parser.parse_args(argv)
    except SystemExit as exc:
        return int(exc.code) if isinstance(exc.code, int) else 2

    try:
        return args.func(args)
    except AuthEcnuError as exc:
        output = getattr(args, "output", "rich") or "rich"
        command = getattr(args, "command", "") or ""
        render_error(exc, output, command=command)
        return exc.exit_code
    except ValueError as exc:
        # Defensive: any uncaught model-level ValueError surfaces as a usage error.
        wrapped = UsageError(str(exc))
        output = getattr(args, "output", "rich") or "rich"
        command = getattr(args, "command", "") or ""
        render_error(wrapped, output, command=command)
        return wrapped.exit_code


if __name__ == "__main__":
    raise SystemExit(main())
