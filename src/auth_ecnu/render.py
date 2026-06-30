"""Output rendering for human and machine-facing CLI modes.

Visual palette is deliberately hacker-terminal-ish: bright green as the
primary, magenta to spotlight cryptographic fields (hashes, encoded
payloads), red for alerts, cyan/dim-green for ambient labels.
"""

from __future__ import annotations

import json
import sys
from contextlib import contextmanager
from typing import Any, Iterator, Mapping

from . import __version__
from .constants import JSON_SCHEMA_VERSION
from .errors import AuthEcnuError
from .models import OnlineStatus
from .protocol import online_status_to_dict, query_string

try:
    from rich import box
    from rich.console import Console
    from rich.panel import Panel
    from rich.syntax import Syntax
    from rich.table import Table
except ImportError:  # pragma: no cover - exercised only when rich is missing.
    Console = None  # type: ignore[assignment]
    Panel = None  # type: ignore[assignment]
    Syntax = None  # type: ignore[assignment]
    Table = None  # type: ignore[assignment]
    box = None  # type: ignore[assignment]


HACKER_BORDER = "bright_green"
HACKER_DIM = "dim green"
HACKER_FIELD = "bold bright_green"
HACKER_VALUE = "green"
HACKER_ALERT = "bold red"
HACKER_PANEL = "black on green"
HACKER_HASH = "bold magenta"
HACKER_INFO = "cyan"
HACKER_WARN = "yellow"

# Fields that should be rendered as cryptographic material (magenta hash).
HASH_FIELDS = frozenset({"chksum", "info", "password"})


def build_meta(command: str = "") -> dict[str, Any]:
    """Return the meta block stamped on every JSON document.

    Downstream scripts should branch on ``schema_version`` if they need
    to support multiple versions of this tool.
    """
    return {
        "tool": "auth_ecnu",
        "version": __version__,
        "command": command,
        "schema_version": JSON_SCHEMA_VERSION,
    }


def _emit_json(payload: dict[str, Any], *, stream: Any = None) -> None:
    text = json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True)
    if stream is None:
        print(text)
    else:
        print(text, file=stream)


def print_json(value: Any) -> None:
    """Legacy helper: emit a JSON document to stdout."""
    print(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True))


def print_data(data: dict[str, Any], command: str) -> None:
    payload = dict(data)
    payload["meta"] = build_meta(command)
    _emit_json(payload)


def print_error(error: BaseException, command: str = "") -> None:
    """Emit a structured JSON error envelope to stderr."""
    code = getattr(error, "code", "error")
    payload = {
        "error": {
            "code": code,
            "message": str(error),
        },
        "meta": build_meta(command),
    }
    _emit_json(payload, stream=sys.stderr)


def rich_available() -> bool:
    return Console is not None


def _console(stderr: bool = False) -> Any:
    if Console is None:
        return None
    return Console(stderr=stderr)


@contextmanager
def network_step(label: str, output: str) -> Iterator[None]:
    """Show a hacker-styled spinner around a network call.

    No-op in JSON mode or when rich is unavailable. ``rich``'s spinner
    auto-hides on non-tty streams so this is also safe under test capture.
    """
    if output != "rich" or Console is None:
        yield
        return
    console = _console(stderr=True)
    with console.status(
        f"[{HACKER_INFO}]>>>[/] [{HACKER_DIM}]{label}…[/]",
        spinner="dots",
        spinner_style=HACKER_BORDER,
    ):
        yield


def _terminal_title(title: str) -> str:
    return f"[{HACKER_PANEL}] {title.upper()} [/]"


def _state_label(enabled: bool) -> str:
    return "[bold bright_green][ONLINE][/]" if enabled else "[bold red][OFFLINE][/]"


def _value(value: Any) -> str:
    text = str(value) if value not in (None, "") else "-"
    return f"[{HACKER_VALUE}]{text}[/]"


def _hash_value(value: Any) -> str:
    text = str(value) if value not in (None, "") else "-"
    return f"[{HACKER_HASH}]{text}[/]"


def _jsonish(value: Any) -> str:
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False)
    return str(value)


def status_payload(status: OnlineStatus) -> dict[str, Any]:
    return online_status_to_dict(status)


def render_status(status: OnlineStatus, output: str, command: str = "check") -> None:
    payload = status_payload(status)
    if output == "json":
        print_data(payload, command)
        return

    console = _console()
    if console is None:
        print(f"Online: {'yes' if status.online else 'no'}")
        if status.username:
            print(f"Username: {status.username}")
        if payload.get("ip"):
            print(f"IP: {payload['ip']}")
        return

    table = Table(box=box.HEAVY, show_header=False, pad_edge=True)
    table.add_column("FIELD", style=HACKER_FIELD, no_wrap=True)
    table.add_column("VALUE", style=HACKER_VALUE)
    table.add_row("STATE", _state_label(status.online))
    table.add_row("USER", _value(status.username))
    table.add_row("IP", _value(payload.get("ip")))
    console.print(
        Panel(
            table,
            title=_terminal_title("ECNU NET STATUS"),
            subtitle=f"[{HACKER_DIM}]rad_user_info[/]",
            border_style=HACKER_BORDER if status.online else HACKER_ALERT,
        )
    )


def auth_response_payload(body: str, decoder: Any) -> dict[str, Any]:
    try:
        decoded = decoder(body)
    except Exception:
        return {"raw": body}
    return decoded


def _decode_failed(payload: Mapping[str, Any]) -> bool:
    return list(payload.keys()) == ["raw"]


def render_auth_response(title: str, body: str, output: str, decoder: Any, command: str = "") -> None:
    payload = auth_response_payload(body, decoder)
    if output == "json":
        print_data(payload, command)
        return

    console = _console()
    if console is None:
        print(title)
        for key, value in payload.items():
            print(f"{key}: {value}")
        return

    decode_failed = _decode_failed(payload)
    table = Table(box=box.HEAVY, show_header=False, pad_edge=True)
    table.add_column("FIELD", style=HACKER_FIELD, no_wrap=True)
    table.add_column("VALUE", style=HACKER_VALUE)
    for key, value in payload.items():
        cell = _hash_value(value) if key.lower() in HASH_FIELDS else _value(_jsonish(value))
        table.add_row(str(key).upper(), cell)

    if decode_failed:
        subtitle = f"[{HACKER_ALERT}][DECODE FAIL][/] [{HACKER_DIM}]raw body shown[/]"
        border = HACKER_ALERT
    else:
        subtitle = f"[{HACKER_DIM}]portal response[/]"
        border = HACKER_BORDER

    console.print(
        Panel(
            table,
            title=_terminal_title(title),
            subtitle=subtitle,
            border_style=border,
        )
    )


def request_payload(request: Mapping[str, str]) -> dict[str, Any]:
    return {
        "request": dict(request),
        "query": query_string(request),
    }


def render_request(title: str, request: Mapping[str, str], output: str, command: str = "") -> None:
    payload = request_payload(request)
    if output == "json":
        print_data(payload, command)
        return

    console = _console()
    if console is None:
        print(title)
        print(f"Action: {request.get('action', '-')}")
        print(f"Username: {request.get('username', '-')}")
        print(f"AC ID: {request.get('ac_id', '-')}")
        print(f"IP: {request.get('ip', '-')}")
        print(f"Checksum: {request.get('chksum', '-')}")
        print()
        print(payload["query"])
        return

    table = Table(box=box.HEAVY, show_header=False, pad_edge=True)
    table.add_column("FIELD", style=HACKER_FIELD, no_wrap=True)
    table.add_column("VALUE", style=HACKER_VALUE)
    table.add_row("ACTION", _value(request.get("action")))
    table.add_row("USER", _value(request.get("username")))
    table.add_row("AC_ID", _value(request.get("ac_id")))
    table.add_row("IP", _value(request.get("ip")))
    table.add_row("SHA1", _hash_value(request.get("chksum")))
    info_value = request.get("info")
    if info_value:
        table.add_row("INFO", _hash_value(_ellipsize(info_value, 60)))
    console.print(
        Panel(
            table,
            title=_terminal_title(title),
            subtitle=f"[{HACKER_WARN}]preview only:[/] [{HACKER_DIM}]not submitted[/]",
            border_style=HACKER_BORDER,
        )
    )
    console.print(
        Panel(
            Syntax(payload["query"], "text", theme="monokai", word_wrap=True),
            title=_terminal_title("QUERY PAYLOAD"),
            border_style=HACKER_DIM,
        )
    )


def _ellipsize(value: str, max_len: int) -> str:
    if len(value) <= max_len:
        return value
    head = max_len - 3
    return f"{value[:head]}..."


def render_error(error: AuthEcnuError, output: str, command: str = "") -> None:
    """Top-level error rendering. JSON mode emits an error envelope;
    rich/plain mode prints a styled banner to stderr."""
    if output == "json":
        print_error(error, command)
        return

    console = _console(stderr=True)
    if console is None:
        print(f"error: {error}", file=sys.stderr)
        return

    code = getattr(error, "code", "error")
    table = Table(box=box.HEAVY, show_header=False, pad_edge=True)
    table.add_column("FIELD", style=HACKER_FIELD, no_wrap=True)
    table.add_column("VALUE", style=HACKER_VALUE)
    table.add_row("CODE", f"[{HACKER_ALERT}]{code}[/]")
    table.add_row("DETAIL", f"[{HACKER_WARN}]{error}[/]")
    console.print(
        Panel(
            table,
            title=_terminal_title("AUTH_ECNU FAULT"),
            subtitle=f"[{HACKER_DIM}]see --help or README for usage[/]",
            border_style=HACKER_ALERT,
        )
    )


def render_banner(output: str) -> None:
    """Print a small hacker-style banner."""
    if output == "json":
        print_data({"banner": _BANNER_TEXT}, "banner")
        return
    console = _console()
    if console is None:
        print(_BANNER_TEXT)
        return
    console.print(
        Panel(
            f"[{HACKER_HASH}]{_BANNER_TEXT}[/]\n"
            f"[{HACKER_DIM}]ECNU/SRun campus auth client · "
            f"v{__version__} · schema {JSON_SCHEMA_VERSION}[/]",
            title=_terminal_title("AUTH_ECNU"),
            subtitle=f"[{HACKER_INFO}]> ready[/]",
            border_style=HACKER_BORDER,
        )
    )


_BANNER_TEXT = r"""
   ___       __  __  ___  ___ _  _ _   _
  / _ \ /\ /\\ \/ / / _ \/ __| \| | | | |
 | |_| / // / >  < |  __/ (__| .` | |_| |
  \___/\_, /_/\_\  \___|\___|_|\_|\___/
       /__/
""".strip("\n")
