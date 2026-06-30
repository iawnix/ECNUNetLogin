"""Output rendering for human and machine-facing CLI modes.

Layout is deliberately minimal — no nested boxes, no panels. Each
logical block prints a single-line section header (``> TITLE · sub``)
followed by indented field rows, the way real terminal tooling (nmap,
msfconsole, neofetch) lays out its scrollback. Colour does all the
visual lifting:

- ``bright_green``   primary
- ``dim green``      labels, subtitles, dimmed wire payloads
- ``bold magenta``   cryptographic material (chksum, info, password)
- ``bold red``       errors and offline state
- ``yellow``         warnings, preview-mode advisories
- ``cyan``           informational hints (spinner prefix)
"""

from __future__ import annotations

import json
import sys
import textwrap
from contextlib import contextmanager
from typing import Any, Iterator, Mapping

from . import __version__
from .constants import JSON_SCHEMA_VERSION
from .errors import AuthEcnuError
from .models import OnlineStatus
from .protocol import online_status_to_dict, query_string

try:
    from rich.console import Console
except ImportError:  # pragma: no cover - exercised only when rich is missing.
    Console = None  # type: ignore[assignment]


HACKER_BORDER = "bright_green"
HACKER_DIM = "dim green"
HACKER_FIELD = "bold bright_green"
HACKER_VALUE = "green"
HACKER_ALERT = "bold red"
HACKER_HASH = "bold magenta"
HACKER_INFO = "cyan"
HACKER_WARN = "yellow"

# Fields rendered as cryptographic material (magenta).
HASH_FIELDS = frozenset({"chksum", "info", "password"})

INDENT = "  "
WRAP_WIDTH = 78


# ---------------------------------------------------------------------------
# JSON envelope helpers
# ---------------------------------------------------------------------------


def build_meta(command: str = "") -> dict[str, Any]:
    """Return the meta block stamped on every JSON document."""
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


def print_data(data: dict[str, Any], command: str) -> None:
    payload = dict(data)
    payload["meta"] = build_meta(command)
    _emit_json(payload)


def print_error(error: BaseException, command: str = "") -> None:
    """Emit a structured JSON error envelope to stderr."""
    code = getattr(error, "code", "error")
    payload = {
        "error": {"code": code, "message": str(error)},
        "meta": build_meta(command),
    }
    _emit_json(payload, stream=sys.stderr)


# ---------------------------------------------------------------------------
# Rich infrastructure
# ---------------------------------------------------------------------------


def rich_available() -> bool:
    return Console is not None


def _console(stderr: bool = False) -> Any:
    if Console is None:
        return None
    return Console(stderr=stderr)


@contextmanager
def network_step(label: str, output: str) -> Iterator[None]:
    """Hacker-styled spinner around a network call.

    No-op in JSON mode or when rich is unavailable. Rich's spinner
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


# ---------------------------------------------------------------------------
# Section primitives
# ---------------------------------------------------------------------------


def _section(
    console: Any,
    title: str,
    *,
    subtitle: str | None = None,
    mark: str = ">",
    mark_style: str = HACKER_BORDER,
    title_style: str = HACKER_FIELD,
    subtitle_style: str = HACKER_DIM,
) -> None:
    """Print a one-line section header: ``[mark] TITLE · subtitle``."""
    line = f"[{mark_style}]{mark}[/] [{title_style}]{title}[/]"
    if subtitle:
        line += f" [{subtitle_style}]· {subtitle}[/]"
    console.print(line)


def _print_rows(console: Any, rows: list[tuple[str, str]]) -> None:
    """Print ``label  value`` rows with the label column right-padded to align.

    Each row already carries Rich markup on the value side; the label is
    coloured by ``HACKER_FIELD`` here.
    """
    if not rows:
        return
    width = max(len(label) for label, _ in rows)
    for label, value in rows:
        console.print(
            f"{INDENT}[{HACKER_FIELD}]{label.ljust(width)}[/]  {value}"
        )


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


def _ellipsize(value: str, max_len: int) -> str:
    if len(value) <= max_len:
        return value
    return f"{value[: max_len - 3]}..."


# ---------------------------------------------------------------------------
# Status block
# ---------------------------------------------------------------------------


def status_payload(status: OnlineStatus) -> dict[str, Any]:
    return online_status_to_dict(status)


def render_status(
    status: OnlineStatus,
    output: str,
    command: str = "check",
    *,
    host: str = "",
) -> None:
    payload = status_payload(status)
    if output == "quiet":
        return
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

    mark_style = HACKER_BORDER if status.online else HACKER_ALERT
    subtitle = f"portal={host}" if host else "portal status"
    _section(
        console,
        "ECNU NET STATUS",
        subtitle=subtitle,
        mark_style=mark_style,
    )
    _print_rows(
        console,
        [
            ("STATE", _state_label(status.online)),
            ("USER", _value(status.username)),
            ("IP", _value(payload.get("ip"))),
        ],
    )


# ---------------------------------------------------------------------------
# Auth response block
# ---------------------------------------------------------------------------


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
    if output == "quiet":
        return
    if output == "json":
        print_data(payload, command)
        return

    console = _console()
    if console is None:
        print(title)
        for key, value in payload.items():
            print(f"{key}: {value}")
        return

    if _decode_failed(payload):
        _section(
            console,
            f"{title.upper()} [DECODE FAIL]",
            subtitle="raw body shown",
            mark="!",
            mark_style=HACKER_ALERT,
            title_style=HACKER_ALERT,
            subtitle_style=HACKER_WARN,
        )
    else:
        _section(console, title.upper(), subtitle="portal response")

    rows: list[tuple[str, str]] = []
    for key, value in payload.items():
        cell = _hash_value(value) if key.lower() in HASH_FIELDS else _value(_jsonish(value))
        rows.append((str(key).upper(), cell))
    _print_rows(console, rows)


# ---------------------------------------------------------------------------
# Signed-request preview block
# ---------------------------------------------------------------------------


def request_payload(request: Mapping[str, str]) -> dict[str, Any]:
    return {
        "request": dict(request),
        "query": query_string(request),
    }


def render_request(title: str, request: Mapping[str, str], output: str, command: str = "") -> None:
    payload = request_payload(request)
    if output == "quiet":
        return
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

    _section(
        console,
        title.upper(),
        subtitle="preview only (not submitted)",
        subtitle_style=HACKER_WARN,
    )
    rows: list[tuple[str, str]] = [
        ("ACTION", _value(request.get("action"))),
        ("USER", _value(request.get("username"))),
        ("AC_ID", _value(request.get("ac_id"))),
        ("IP", _value(request.get("ip"))),
        ("SHA1", _hash_value(request.get("chksum"))),
    ]
    info_value = request.get("info")
    if info_value:
        rows.append(("INFO", _hash_value(_ellipsize(info_value, 64))))
    _print_rows(console, rows)

    console.print()
    query = payload["query"]
    _section(console, "QUERY PAYLOAD", subtitle=f"{len(query)} bytes")
    for line in textwrap.wrap(query, width=WRAP_WIDTH, break_long_words=True, break_on_hyphens=False):
        console.print(f"{INDENT}[{HACKER_DIM}]{line}[/]")


# ---------------------------------------------------------------------------
# Error & banner blocks
# ---------------------------------------------------------------------------


def render_error(error: AuthEcnuError, output: str, command: str = "") -> None:
    """Top-level error rendering. JSON mode emits an error envelope;
    rich mode prints a hacker-style fault line to stderr; quiet mode is silent."""
    if output == "quiet":
        return
    if output == "json":
        print_error(error, command)
        return

    console = _console(stderr=True)
    if console is None:
        print(f"error: {error}", file=sys.stderr)
        return

    code = getattr(error, "code", "error")
    _section(
        console,
        "AUTH_ECNU FAULT",
        subtitle=code,
        mark="!",
        mark_style=HACKER_ALERT,
        title_style=HACKER_ALERT,
        subtitle_style=HACKER_WARN,
    )
    console.print(f"{INDENT}[{HACKER_WARN}]{error}[/]", soft_wrap=True)


def render_banner(output: str) -> None:
    """Hacker-style ASCII banner. JSON mode emits the raw text under a key."""
    if output == "quiet":
        return
    if output == "json":
        print_data({"banner": _BANNER_TEXT}, "banner")
        return
    console = _console()
    if console is None:
        print(_BANNER_TEXT)
        return
    for line in _BANNER_TEXT.splitlines():
        console.print(f"[{HACKER_HASH}]{line}[/]")
    console.print(
        f"[{HACKER_BORDER}]>[/] [{HACKER_FIELD}]auth_ecnu[/] "
        f"[{HACKER_DIM}]v{__version__} · schema {JSON_SCHEMA_VERSION} · ECNU/SRun campus auth[/]"
    )


_BANNER_TEXT = r"""
   ___       __  __  ___  ___ _  _ _   _
  / _ \ /\ /\\ \/ / / _ \/ __| \| | | | |
 | |_| / // / >  < |  __/ (__| .` | |_| |
  \___/\_, /_/\_\  \___|\___|_|\_|\___/
       /__/
""".strip("\n")
