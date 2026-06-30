"""Command-line interface for auth_ecnu."""

from __future__ import annotations

import argparse
import getpass
import sys
from typing import Sequence

from . import __version__
from .client import SrunClient, decode_jsonp_or_json
from .config import AuthSetting, default_config_path, load_auth_setting
from .constants import DEFAULT_TIMEOUT
from .errors import AuthEcnuError, UsageError
from .models import OnlineStatus, SrunUrlProvider
from .render import (
    auth_response_payload,
    network_step,
    print_data,
    render_auth_response,
    render_banner,
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
    if hasattr(args, "username") and not getattr(args, "username", None) and setting.username:
        args.username = setting.username
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
        render_status(status, args.output, command=command)
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
        render_status(status, args.output, command=command)
    return 0


def run_check(args: argparse.Namespace) -> int:
    apply_config_defaults(args)
    client = make_client(args)
    with network_step("querying rad_user_info", args.output):
        status = client.check_online_status()
    render_status(status, args.output, command=_command_name(args))
    return 0


def run_banner(args: argparse.Namespace) -> int:
    render_banner(args.output)
    return 0


def add_config_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--config",
        "-c",
        default=None,
        help=(
            "path to an auth-setting file (host, acid, campus_postfix, campus_url, "
            f"username). Defaults to {default_config_path()} with a legacy "
            f"~/.auth-setting fallback."
        ),
    )


def add_common_network_args(parser: argparse.ArgumentParser) -> None:
    add_config_args(parser)
    parser.add_argument("--host", "-H", help="SRun portal host, e.g. 10.0.0.1")
    parser.add_argument("--timeout", type=float, default=DEFAULT_TIMEOUT, help="HTTP timeout in seconds")
    parser.add_argument("--debug", "-d", action="store_true", help="print HTTP requests to stderr")


def add_identity_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--username", "-u", required=False, help="account name (falls back to config)")
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


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="auth_ecnu",
        description=CLI_DESCRIPTION,
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--version", "-V", action="version", version=f"auth_ecnu {__version__}")
    subparsers = parser.add_subparsers(dest="command", required=True)

    for name, helptext in (("login", "fetch token, build request, and submit login"),
                           ("auth", "alias for login")):
        sub = subparsers.add_parser(name, help=helptext)
        add_common_network_args(sub)
        add_identity_args(sub)
        add_password_args(sub)
        add_output_args(sub)
        add_request_build_args(sub, default_action="login")
        add_auth_flow_args(sub)
        sub.set_defaults(func=run_login)

    logout = subparsers.add_parser("logout", help="fetch token, build request, and submit logout")
    add_common_network_args(logout)
    add_identity_args(logout)
    add_output_args(logout)
    add_request_build_args(logout, default_action="logout")
    add_auth_flow_args(logout)
    logout.set_defaults(func=run_logout)

    for name, helptext in (("check", "query /cgi-bin/rad_user_info"),
                           ("status", "alias for check")):
        sub = subparsers.add_parser(name, help=helptext)
        add_common_network_args(sub)
        add_output_args(sub)
        sub.set_defaults(func=run_check)

    banner = subparsers.add_parser("banner", help="print the auth_ecnu ASCII banner")
    add_output_args(banner)
    banner.set_defaults(func=run_banner)

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
        # argparse already printed its message; pass through its exit code.
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
