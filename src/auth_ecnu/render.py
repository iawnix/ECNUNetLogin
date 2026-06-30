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


def print_json(value: Any) -> None:
    print(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True))


def rich_available() -> bool:
    return Console is not None


def _console() -> Any:
    if Console is None:
        return None
    return Console()


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

    table = Table(box=box.SIMPLE, show_header=False)
    table.add_column("Field", style="cyan", no_wrap=True)
    table.add_column("Value")
    table.add_row("Online", "yes" if status.online else "no")
    table.add_row("Username", status.username or "-")
    table.add_row("IP", str(payload.get("ip") or "-"))
    console.print(Panel(table, title="ECNU Network Status", border_style="green" if status.online else "red"))


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

    table = Table(box=box.SIMPLE, show_header=False)
    table.add_column("Field", style="cyan", no_wrap=True)
    table.add_column("Value")
    for key, value in payload.items():
        table.add_row(str(key), json.dumps(value, ensure_ascii=False) if isinstance(value, (dict, list)) else str(value))
    console.print(Panel(table, title=title, border_style="blue"))


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

    table = Table(box=box.SIMPLE, show_header=False)
    table.add_column("Field", style="cyan", no_wrap=True)
    table.add_column("Value")
    table.add_row("Action", request.get("action", "-"))
    table.add_row("Username", request.get("username", "-"))
    table.add_row("AC ID", request.get("ac_id", "-"))
    table.add_row("IP", request.get("ip", "-"))
    table.add_row("Checksum", request.get("chksum", "-"))
    console.print(Panel(table, title=title, border_style="blue"))
    console.print(Panel(Syntax(payload["query"], "text", word_wrap=True), title="Query String", border_style="dim"))
