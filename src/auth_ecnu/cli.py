"""Command-line interface for auth_ecnu."""

from __future__ import annotations

import argparse
import getpass
import sys
from typing import Sequence

from .client import SrunClient, decode_jsonp_or_json
from .config import DEFAULT_CONFIG_PATH, AuthSetting, load_auth_setting
from .constants import DEFAULT_TIMEOUT
from .errors import CliError
from .models import OnlineStatus, SrunUrlProvider
from .render import (
    auth_response_payload,
    print_json,
    render_auth_response,
    render_request,
    render_status,
    status_payload,
)


CLI_DESCRIPTION = (
    "Built by iaw and Codex as a Python refactor of the existing ECNU auth_client "
    "for campus network login, logout, request signing, and online status checks."
)


def normalize_username(username: str, campus_postfix: str = "") -> str:
    if not username:
        raise CliError("username is required")
    if campus_postfix and not username.endswith(campus_postfix):
        return f"{username}{campus_postfix}"
    return username


def resolve_password(args: argparse.Namespace, *, required: bool) -> str:
    password = getattr(args, "password", None) or ""
    if getattr(args, "password_stdin", False):
        stdin_value = sys.stdin.read().rstrip("\r\n")
        if password:
            raise CliError("--password and --password-stdin cannot be used together")
        password = stdin_value
    if getattr(args, "ask_password", False):
        if password:
            raise CliError("--password/--password-stdin and --ask-password cannot be used together")
        password = getpass.getpass("Password: ")
    if required and not password:
        raise CliError("password is required for login; use --password, --password-stdin, or --ask-password")
    return password


def apply_config_defaults(args: argparse.Namespace) -> AuthSetting:
    setting = load_auth_setting(getattr(args, "config", DEFAULT_CONFIG_PATH))
    if hasattr(args, "host") and not getattr(args, "host", None) and setting.host:
        args.host = setting.host
    if hasattr(args, "acid") and getattr(args, "acid", None) is None and setting.acid is not None:
        args.acid = setting.acid
    if hasattr(args, "campus_postfix") and not getattr(args, "campus_postfix", "") and setting.campus_postfix:
        args.campus_postfix = setting.campus_postfix
    return setting


def make_provider(args: argparse.Namespace) -> SrunUrlProvider:
    if not getattr(args, "host", None):
        raise CliError(f"--host is required; pass --host or set host in {getattr(args, 'config', DEFAULT_CONFIG_PATH)}")
    return SrunUrlProvider.from_host(args.host)


def make_client(args: argparse.Namespace) -> SrunClient:
    return SrunClient(
        make_provider(args),
        timeout=getattr(args, "timeout", DEFAULT_TIMEOUT),
        debug=getattr(args, "debug", False),
    )


def print_request(request: dict[str, str], output: str) -> None:
    render_request("Signed Request", request, output)


def print_auth_response(title: str, body: str, output: str) -> None:
    render_auth_response(title, body, output, decode_jsonp_or_json)


def print_online_status(status: OnlineStatus, output: str) -> None:
    render_status(status, output)


def run_login(args: argparse.Namespace) -> int:
    apply_config_defaults(args)
    password = resolve_password(args, required=True)
    username = normalize_username(args.username, args.campus_postfix)
    client = make_client(args)
    request = client.build_auth_request(
        username=username,
        password=password,
        action="login",
        ip=args.ip,
        acid=args.acid,
        token=args.token,
        include_callback=True,
    )
    if args.preview:
        print_request(request, args.output)
        return 0
    result = client.submit_auth(request)
    if args.output == "json" and args.check_after:
        print_json(
            {
                "response": auth_response_payload(result.body, decode_jsonp_or_json),
                "status": status_payload(client.check_online_status()),
            }
        )
        return 0
    print_auth_response("Login Response", result.body, args.output)
    if args.check_after:
        print()
        print_online_status(client.check_online_status(), args.output)
    return 0


def run_logout(args: argparse.Namespace) -> int:
    apply_config_defaults(args)
    username = normalize_username(args.username, args.campus_postfix)
    client = make_client(args)
    request = client.build_auth_request(
        username=username,
        password="",
        action="logout",
        ip=args.ip,
        acid=args.acid,
        token=args.token,
        include_callback=True,
    )
    if args.preview:
        print_request(request, args.output)
        return 0
    result = client.submit_auth(request)
    if args.output == "json" and args.check_after:
        print_json(
            {
                "response": auth_response_payload(result.body, decode_jsonp_or_json),
                "status": status_payload(client.check_online_status()),
            }
        )
        return 0
    print_auth_response("Logout Response", result.body, args.output)
    if args.check_after:
        print()
        print_online_status(client.check_online_status(), args.output)
    return 0


def run_check(args: argparse.Namespace) -> int:
    apply_config_defaults(args)
    print_online_status(make_client(args).check_online_status(), args.output)
    return 0


def add_config_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--config",
        "-c",
        default=str(DEFAULT_CONFIG_PATH),
        help="auth setting file with host, acid, campus_postfix, and campus_url",
    )


def add_common_network_args(parser: argparse.ArgumentParser) -> None:
    add_config_args(parser)
    parser.add_argument("--host", "-H", help="SRun portal host, e.g. 10.0.0.1")
    parser.add_argument("--timeout", type=float, default=DEFAULT_TIMEOUT, help="HTTP timeout in seconds")
    parser.add_argument("--debug", "-d", action="store_true", help="print HTTP requests to stderr")


def add_identity_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--username", "-u", required=False, help="account name")
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
        choices=("rich", "json"),
        default="rich",
        help="render human-friendly rich output or machine-readable JSON",
    )
    parser.add_argument(
        "--json",
        dest="output",
        action="store_const",
        const="json",
        help="shortcut for --output json",
    )
    parser.add_argument(
        "--no-rich",
        dest="output",
        action="store_const",
        const="json",
        help=argparse.SUPPRESS,
    )


def add_request_build_args(parser: argparse.ArgumentParser, *, default_action: str | None = None) -> None:
    if default_action is None:
        parser.add_argument("--action", choices=("login", "logout"), required=True)
    parser.add_argument("--token", help=argparse.SUPPRESS)
    parser.add_argument("--ip", default="", help="client IP; empty lets the portal infer it if supported")
    parser.add_argument("--acid", type=int, help="portal ac_id; defaults to config or auto-detect in host mode")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="auth_ecnu",
        description=CLI_DESCRIPTION,
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    login = subparsers.add_parser("login", help="fetch token, build request, and submit login")
    add_common_network_args(login)
    add_identity_args(login)
    add_password_args(login)
    add_output_args(login)
    add_request_build_args(login, default_action="login")
    login.add_argument("--preview", action="store_true", help="print the signed request without submitting it")
    login.add_argument("--check-after", action="store_true", help="query online status after login")
    login.set_defaults(func=run_login)

    auth = subparsers.add_parser("auth", help="alias for login")
    add_common_network_args(auth)
    add_identity_args(auth)
    add_password_args(auth)
    add_output_args(auth)
    add_request_build_args(auth, default_action="login")
    auth.add_argument("--preview", action="store_true", help="print the signed request without submitting it")
    auth.add_argument("--check-after", action="store_true", help="query online status after login")
    auth.set_defaults(func=run_login)

    logout = subparsers.add_parser("logout", help="fetch token, build request, and submit logout")
    add_common_network_args(logout)
    add_identity_args(logout)
    add_output_args(logout)
    add_request_build_args(logout, default_action="logout")
    logout.add_argument("--preview", action="store_true", help="print the signed request without submitting it")
    logout.add_argument("--check-after", action="store_true", help="query online status after logout")
    logout.set_defaults(func=run_logout)

    check = subparsers.add_parser("check", help="query /cgi-bin/rad_user_info")
    add_common_network_args(check)
    add_output_args(check)
    check.set_defaults(func=run_check)

    return parser


def main(argv: Sequence[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    try:
        parser = build_parser()
        if not argv:
            parser.print_help()
            return 0
        args = parser.parse_args(argv)
        return args.func(args)
    except CliError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
