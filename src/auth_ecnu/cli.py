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
        "# Pass -u/--ask-password at runtime, or use --in-json with a\n"
        "# file you keep private (chmod 600).\n"
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
# input-template subcommand
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
def run_input_template(args: argparse.Namespace) -> int:
    action = args.template_action
    template = _INPUT_TEMPLATES.get(action)
    if template is None:
        raise UsageError(
            f"no template for action={action!r}; choose from "
            f"{sorted(_INPUT_TEMPLATES)}"
        )
    # Raw print so the JSON is copy-pasteable straight into a file.
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


def add_output_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--output",
        choices=("rich", "json", "quiet"),
        default="rich",
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


def add_in_json_arg(parser: argparse.ArgumentParser) -> None:
    """Declare --in-json for help display only.

    The flag is actually consumed by :func:`_expand_in_json` before
    argparse runs, so the value stored here is always ``None``. Keeping
    it on every parser ensures ``--help`` mentions it.
    """
    parser.add_argument(
        "--in-json",
        metavar="FILE",
        default=None,
        help="JSON file with run parameters; CLI flags override its values",
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="auth_ecnu",
        description=CLI_DESCRIPTION,
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--version", "-V", action="version", version=f"auth_ecnu {__version__}")
    add_in_json_arg(parser)
    subparsers = parser.add_subparsers(dest="command", required=True)

    login = subparsers.add_parser("login", help="fetch token, build request, and submit login")
    add_common_network_args(login)
    add_identity_args(login)
    add_password_args(login)
    add_output_args(login)
    add_request_build_args(login, default_action="login")
    add_auth_flow_args(login)
    add_in_json_arg(login)
    login.set_defaults(func=run_login)

    logout = subparsers.add_parser("logout", help="fetch token, build request, and submit logout")
    add_common_network_args(logout)
    add_identity_args(logout)
    add_output_args(logout)
    add_request_build_args(logout, default_action="logout")
    add_auth_flow_args(logout)
    add_in_json_arg(logout)
    logout.set_defaults(func=run_logout)

    check = subparsers.add_parser("check", help="query /cgi-bin/rad_user_info")
    add_common_network_args(check)
    add_output_args(check)
    add_in_json_arg(check)
    check.set_defaults(func=run_check)

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
        help="print a --in-json template for an action",
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


# ---------------------------------------------------------------------------
# --in-json pre-processing
# ---------------------------------------------------------------------------

_TOP_LEVEL_SUBCOMMANDS = (
    "login", "logout", "check",
    "config", "input-template",
)
_JSON_ACTIONS = ("login", "logout", "check")

# JSON key → CLI flag (value-taking)
_JSON_VALUE_FLAGS = {
    "host":           "--host",
    "username":       "--username",
    "password":       "--password",
    "campus_postfix": "--campus-postfix",
    "ip":             "--ip",
    "acid":           "--acid",
    "config":         "--config",
    "timeout":        "--timeout",
    "token":          "--token",
    "output":         "--output",
}

# JSON key → CLI flag (boolean store_true)
_JSON_BOOL_FLAGS = {
    "preview":        "--preview",
    "check_after":    "--check-after",
    "debug":          "--debug",
    "ask_password":   "--ask-password",
    "password_stdin": "--password-stdin",
}

# Flags that consume the next argv token as their value (for subcommand sniffing).
_VALUE_TAKING_FLAGS = frozenset({
    "--config", "-c",
    "--host", "-H",
    "--timeout",
    "--output",
    "--username", "-u",
    "--campus-postfix",
    "--password", "-p",
    "--token",
    "--ip",
    "--acid",
    "--in-json",
})


def _load_in_json(path: str) -> dict[str, Any]:
    try:
        text = Path(path).expanduser().read_text(encoding="utf-8")
    except OSError as exc:
        raise UsageError(f"could not read --in-json file {path!r}: {exc}") from exc
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise UsageError(f"--in-json file {path!r} is not valid JSON: {exc}") from exc
    if not isinstance(data, dict):
        raise UsageError(f"--in-json file {path!r} must be a JSON object")
    schema = data.get("schema_version")
    if schema is not None and schema != 1:
        raise UsageError(
            f"--in-json schema_version {schema!r} not supported (expected 1)"
        )
    return data


def _argv_has_subcommand(argv: Sequence[str]) -> bool:
    skip_next = False
    for tok in argv:
        if skip_next:
            skip_next = False
            continue
        if tok in _VALUE_TAKING_FLAGS:
            skip_next = True
            continue
        if tok.startswith("-"):
            continue
        if tok in _TOP_LEVEL_SUBCOMMANDS:
            return True
    return False


def _argv_specifies(argv: Sequence[str], flag: str, key: str) -> bool:
    if flag in argv:
        return True
    if any(tok.startswith(flag + "=") for tok in argv):
        return True
    # --output has two shortcut aliases.
    if key == "output" and any(t in argv for t in ("--json", "--quiet", "-q")):
        return True
    return False


def _preparse_output(argv: Sequence[str]) -> str:
    """Best-effort output mode before argparse and --in-json expansion.

    ``--in-json`` is read before full argparse parsing, so file-load
    failures need a small raw-argv pass to respect ``--json`` and
    ``--quiet`` where possible.
    """
    output = "rich"
    i = 0
    while i < len(argv):
        token = argv[i]
        if token in {"--quiet", "-q"}:
            output = "quiet"
        elif token == "--json":
            output = "json"
        elif token == "--output" and i + 1 < len(argv):
            candidate = argv[i + 1]
            if candidate in {"rich", "json", "quiet"}:
                output = candidate
            i += 1
        elif token.startswith("--output="):
            candidate = token.split("=", 1)[1]
            if candidate in {"rich", "json", "quiet"}:
                output = candidate
        i += 1
    return output


def _expand_in_json(argv: list[str]) -> list[str]:
    """Strip ``--in-json PATH`` from argv and splice JSON fields in.

    CLI tokens already in argv take precedence over JSON-supplied ones.
    Unknown JSON keys are silently ignored for forward compatibility.
    """
    new_argv: list[str] = []
    json_path: str | None = None
    i = 0
    while i < len(argv):
        token = argv[i]
        if token == "--in-json":
            if i + 1 >= len(argv):
                raise UsageError("--in-json requires a file path")
            json_path = argv[i + 1]
            i += 2
            continue
        if token.startswith("--in-json="):
            json_path = token.split("=", 1)[1]
            i += 1
            continue
        new_argv.append(token)
        i += 1

    if json_path is None:
        return argv

    data = _load_in_json(json_path)

    head: list[str] = []
    if not _argv_has_subcommand(new_argv):
        action = data.get("action")
        if not action:
            raise UsageError(
                "--in-json needs either a subcommand on the CLI or an 'action' field in the JSON"
            )
        if action not in _JSON_ACTIONS:
            raise UsageError(
                f"--in-json 'action' must be one of {_JSON_ACTIONS}, got {action!r}"
            )
        head.append(action)

    tail: list[str] = []
    for key, value in data.items():
        if key in ("schema_version", "action"):
            continue
        if key in _JSON_VALUE_FLAGS:
            flag = _JSON_VALUE_FLAGS[key]
            if _argv_specifies(new_argv, flag, key):
                continue
            if value is None or value == "":
                continue
            tail.extend([flag, str(value)])
        elif key in _JSON_BOOL_FLAGS:
            flag = _JSON_BOOL_FLAGS[key]
            if _argv_specifies(new_argv, flag, key):
                continue
            if value:
                tail.append(flag)
        # Unknown keys silently dropped.

    return head + new_argv + tail


def main(argv: Sequence[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    parser = build_parser()
    if not argv:
        parser.print_help()
        return 0

    preparse_output = _preparse_output(argv)
    try:
        argv = _expand_in_json(argv)
    except UsageError as exc:
        render_error(exc, preparse_output, command="")
        return exc.exit_code

    if not argv:
        parser.print_help()
        return 0

    try:
        args = parser.parse_args(argv)
    except SystemExit as exc:
        return int(exc.code) if isinstance(exc.code, int) else 2

    output = getattr(args, "output", "rich")
    command = getattr(args, "command", "") or ""
    try:
        return args.func(args)
    except AuthEcnuError as exc:
        render_error(exc, output, command=command)
        return exc.exit_code
    except ValueError as exc:
        # Defensive: any uncaught model-level ValueError surfaces as a usage error.
        wrapped = UsageError(str(exc))
        render_error(wrapped, output, command=command)
        return wrapped.exit_code


if __name__ == "__main__":
    raise SystemExit(main())
