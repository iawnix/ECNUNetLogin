"""Output rendering for human and machine-facing CLI modes."""

from __future__ import annotations

import json
from typing import Any, Mapping

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


def print_json(value: Any) -> None:
    print(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True))


def rich_available() -> bool:
    return Console is not None


def _console() -> Any:
    if Console is None:
        return None
    return Console()


def _terminal_title(title: str) -> str:
    return f"[{HACKER_PANEL}] {title.upper()} [/]"


def _state_label(enabled: bool) -> str:
    return "[bold bright_green][ONLINE][/]" if enabled else "[bold red][OFFLINE][/]"


def _value(value: Any) -> str:
    text = str(value) if value not in (None, "") else "-"
    return f"[{HACKER_VALUE}]{text}[/]"


def _jsonish(value: Any) -> str:
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False)
    return str(value)


def _status_ip(status: OnlineStatus) -> str:
    fields = status.raw.split(",") if status.raw else []
    if len(fields) > 8 and fields[8]:
        return fields[8]
    return ""


def status_payload(status: OnlineStatus) -> dict[str, Any]:
    payload = online_status_to_dict(status)
    ip = _status_ip(status)
    if ip:
        payload["ip"] = ip
    return payload


def render_status(status: OnlineStatus, output: str) -> None:
    payload = status_payload(status)
    if output == "json":
        print_json(payload)
        return

    console = _console()
    if console is None:
        print(f"Online: {'yes' if status.online else 'no'}")
        if status.username:
            print(f"Username: {status.username}")
        if payload.get("ip"):
            print(f"IP: {payload['ip']}")
        return

    table = Table(box=box.SQUARE, show_header=False, pad_edge=True)
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


def render_auth_response(title: str, body: str, output: str, decoder: Any) -> None:
    payload = auth_response_payload(body, decoder)
    if output == "json":
        print_json(payload)
        return

    console = _console()
    if console is None:
        print(title)
        for key, value in payload.items():
            print(f"{key}: {value}")
        return

    table = Table(box=box.SQUARE, show_header=False, pad_edge=True)
    table.add_column("FIELD", style=HACKER_FIELD, no_wrap=True)
    table.add_column("VALUE", style=HACKER_VALUE)
    for key, value in payload.items():
        table.add_row(str(key).upper(), _value(_jsonish(value)))
    console.print(
        Panel(
            table,
            title=_terminal_title(title),
            subtitle=f"[{HACKER_DIM}]portal response[/]",
            border_style=HACKER_BORDER,
        )
    )


def request_payload(request: Mapping[str, str]) -> dict[str, Any]:
    return {
        "request": dict(request),
        "query": query_string(request),
    }


def render_request(title: str, request: Mapping[str, str], output: str) -> None:
    payload = request_payload(request)
    if output == "json":
        print_json(payload)
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

    table = Table(box=box.SQUARE, show_header=False, pad_edge=True)
    table.add_column("FIELD", style=HACKER_FIELD, no_wrap=True)
    table.add_column("VALUE", style=HACKER_VALUE)
    table.add_row("ACTION", _value(request.get("action")))
    table.add_row("USER", _value(request.get("username")))
    table.add_row("AC_ID", _value(request.get("ac_id")))
    table.add_row("IP", _value(request.get("ip")))
    table.add_row("SHA1", _value(request.get("chksum")))
    console.print(
        Panel(
            table,
            title=_terminal_title(title),
            subtitle=f"[{HACKER_DIM}]preview only: not submitted[/]",
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
