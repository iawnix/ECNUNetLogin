"""Command-line interface for auth_ecnu."""

from __future__ import annotations

import argparse
import getpass
import sys
from typing import Mapping, Sequence

from .client import SrunClient, decode_jsonp_or_json
from .config import DEFAULT_CONFIG_PATH, AuthSetting, load_auth_setting
from .constants import DEFAULT_TIMEOUT
from .errors import CliError
from .models import AuthParams, OnlineStatus, SrunUrlProvider
from .protocol import (
    add_auth_callback,
    build_request_params,
    query_string,
)
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


def print_request(request: Mapping[str, str], output: str, legacy_format: str | None = None) -> None:
    if legacy_format == "json":
        print_json(dict(request))
    elif legacy_format == "query":
        print(query_string(request))
    elif legacy_format == "both":
        print_json(dict(request))
        print()
        print(query_string(request))
    elif legacy_format is not None:
        raise CliError(f"unsupported output format: {legacy_format}")
    else:
        render_request("Signed Request", request, output)


def print_auth_response(title: str, body: str, output: str) -> None:
    render_auth_response(title, body, output, decode_jsonp_or_json)


def print_online_status(status: OnlineStatus, output: str) -> None:
    render_status(status, output)


def run_build(args: argparse.Namespace) -> int:
    apply_config_defaults(args)
    action = args.action
    password = resolve_password(args, required=action == "login")
    username = normalize_username(args.username, args.campus_postfix)
    if args.acid is None:
        raise CliError(f"--acid is required for offline build; pass --acid or set acid in {args.config}")

    try:
        request = build_request_params(
            AuthParams(
                username=username,
                password=password,
                token=args.token,
                action=action,
                ip=args.ip,
                acid=args.acid,
            )
        )
    except ValueError as exc:
        raise CliError(str(exc)) from exc

    if args.callback:
        request = add_auth_callback(request)
    print_request(request, args.output, args.format)
    return 0


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
    if args.dry_run:
        print_request(request, args.output, args.format)
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
    if args.dry_run:
        print_request(request, args.output, args.format)
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
    parser.add_argument("--token", required=default_action is None, help="challenge token")
    parser.add_argument("--ip", default="", help="client IP; empty lets the portal infer it if supported")
    parser.add_argument("--acid", type=int, help="portal ac_id; defaults to config or auto-detect in host mode")
    parser.add_argument(
        "--format",
        choices=("json", "query", "both"),
        default=None,
        help=argparse.SUPPRESS,
    )


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
    login.add_argument("--dry-run", action="store_true", help="print request without submitting it")
    login.add_argument("--check-after", action="store_true", help="query online status after login")
    login.set_defaults(func=run_login)

    auth = subparsers.add_parser("auth", help="alias for login")
    add_common_network_args(auth)
    add_identity_args(auth)
    add_password_args(auth)
    add_output_args(auth)
    add_request_build_args(auth, default_action="login")
    auth.add_argument("--dry-run", action="store_true", help="print request without submitting it")
    auth.add_argument("--check-after", action="store_true", help="query online status after login")
    auth.set_defaults(func=run_login)

    logout = subparsers.add_parser("logout", help="fetch token, build request, and submit logout")
    add_common_network_args(logout)
    add_identity_args(logout)
    add_output_args(logout)
    add_request_build_args(logout, default_action="logout")
    logout.add_argument("--dry-run", action="store_true", help="print request without submitting it")
    logout.add_argument("--check-after", action="store_true", help="query online status after logout")
    logout.set_defaults(func=run_logout)

    check = subparsers.add_parser("check", help="query /cgi-bin/rad_user_info")
    add_common_network_args(check)
    add_output_args(check)
    check.set_defaults(func=run_check)

    build = subparsers.add_parser("build", help="offline request builder; never contacts the portal")
    add_config_args(build)
    add_identity_args(build)
    add_password_args(build)
    add_output_args(build)
    add_request_build_args(build)
    build.add_argument(
        "--callback",
        "--with-callback",
        action="store_true",
        help="include JSONP callback in the auth request",
    )
    build.set_defaults(func=run_build)
    return parser


def build_legacy_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="auth_ecnu",
        description=f"{CLI_DESCRIPTION} Legacy-compatible entrypoint.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    add_config_args(parser)
    parser.add_argument("--host", "-H", help="SRun portal host, e.g. 10.0.0.1")
    parser.add_argument("--username", "-u", help="account name")
    parser.add_argument("--password", "-p", default="", help="account password")
    parser.add_argument("--password-stdin", action="store_true", help="read password from stdin")
    parser.add_argument("--ask-password", action="store_true", help="prompt for password")
    parser.add_argument("--token", help="challenge token from get_challenge; offline mode only")
    parser.add_argument("--ip", default="", help="client IP; empty lets the portal infer it if supported")
    parser.add_argument("--acid", type=int, help="portal ac_id; auto-detected in --host mode if omitted")
    parser.add_argument("--action", choices=("login", "logout"), default="login")
    parser.add_argument("--logout", action="store_true", help="shortcut for --action logout")
    parser.add_argument("--campus", action="store_true", help="legacy no-op; use --campus-postfix")
    parser.add_argument("--campus-postfix", default="", help="append suffix to username")
    parser.add_argument("legacy_command", nargs="?", choices=("auth", "check"))
    parser.add_argument("--with-callback", action="store_true")
    parser.add_argument("--timeout", type=float, default=DEFAULT_TIMEOUT)
    parser.add_argument("--debug", "-d", action="store_true")
    parser.add_argument("--check", action="store_true", help="query /cgi-bin/rad_user_info and exit")
    parser.add_argument("--check-after", action="store_true", help="query online status after login/logout")
    parser.add_argument("--dry-run", action="store_true", help="print auth request without submitting it")
    add_output_args(parser)
    parser.add_argument("--format", choices=("json", "query", "both"), default=None, help=argparse.SUPPRESS)
    return parser


def run_legacy(args: argparse.Namespace, parser: argparse.ArgumentParser) -> int:
    if args.legacy_command == "check":
        args.check = True
    if args.check:
        if not args.host:
            apply_config_defaults(args)
        return run_check(args)

    if not args.username:
        parser.error("--username is required")

    action = "logout" if args.logout else args.action
    args.action = action
    args.callback = args.with_callback or bool(args.host)
    apply_config_defaults(args)

    if args.host:
        if action == "login":
            return run_login(args)
        return run_logout(args)

    if not args.token:
        parser.error("--token is required when --host is not set")
    if args.acid is None:
        parser.error("--acid is required when --host is not set")
    return run_build(args)


def is_modern_cli(argv: Sequence[str]) -> bool:
    commands = {"auth", "login", "logout", "check", "build"}
    return bool(argv) and argv[0] in commands


def main(argv: Sequence[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    try:
        if not argv:
            parser = build_parser()
            parser.print_help()
            return 0
        if argv[0] in {"-h", "--help"} or is_modern_cli(argv):
            args = build_parser().parse_args(argv)
            return args.func(args)
        legacy_parser = build_legacy_parser()
        args = legacy_parser.parse_args(argv)
        return run_legacy(args, legacy_parser)
    except CliError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
