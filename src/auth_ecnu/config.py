"""Compatibility loader for auth_client-style setting files.

The default config location follows the XDG Base Directory specification on
Linux/macOS and uses ``%APPDATA%`` on Windows. The legacy
``~/.auth-setting`` location is still read as a fallback so existing users
keep working without any migration step.
"""

from __future__ import annotations

import dataclasses
import os
import sys
from pathlib import Path
from typing import Iterator

from .errors import UsageError


LEGACY_CONFIG_PATH = Path.home() / ".auth-setting"


def default_config_dir() -> Path:
    """Return the directory the config file should live in.

    Honours ``XDG_CONFIG_HOME`` on POSIX and ``APPDATA`` on Windows so
    tests and packagers can override the location without code changes.
    """
    if sys.platform == "win32":
        appdata = os.environ.get("APPDATA")
        base = Path(appdata) if appdata else Path.home() / "AppData" / "Roaming"
        return base / "auth_ecnu"
    xdg = os.environ.get("XDG_CONFIG_HOME")
    base = Path(xdg).expanduser() if xdg else Path.home() / ".config"
    return base / "auth_ecnu"


def default_config_path() -> Path:
    return default_config_dir() / "setting"


def iter_default_config_paths() -> Iterator[Path]:
    """Yield candidate default paths in priority order (XDG first, legacy last)."""
    primary = default_config_path()
    yield primary
    if LEGACY_CONFIG_PATH != primary:
        yield LEGACY_CONFIG_PATH


def resolve_default_config_path() -> Path | None:
    """Return the first existing default config path, or ``None``."""
    for path in iter_default_config_paths():
        if path.exists():
            return path
    return None


@dataclasses.dataclass(frozen=True)
class AuthSetting:
    host: str = ""
    acid: int | None = None
    campus_postfix: str = ""
    campus_url: str = ""
    username: str = ""


def parse_setting_text(text: str, source: str = "<setting>") -> AuthSetting:
    values: dict[str, str] = {}
    for line_no, raw_line in enumerate(text.splitlines(), start=1):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            raise UsageError(f"invalid config line {source}:{line_no}: {raw_line!r}")
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
            value = value[1:-1]
        values[key] = value

    acid = None
    raw_acid = values.get("acid", "")
    if raw_acid:
        try:
            acid = int(raw_acid, 10)
        except ValueError as exc:
            raise UsageError(f"invalid acid in {source}: {raw_acid!r}") from exc

    return AuthSetting(
        host=values.get("host", ""),
        acid=acid,
        campus_postfix=values.get("campus_postfix", ""),
        campus_url=values.get("campus_url", ""),
        username=values.get("username", ""),
    )


def load_auth_setting(path: str | Path | None) -> AuthSetting:
    """Load an auth-setting file with transparent legacy fallback.

    - ``None`` searches the XDG/AppData default then the legacy ``~/.auth-setting``.
    - An explicit path is read when present; the legacy fallback only kicks in
      if the caller asked for the new default path that happens to not exist
      yet (so first-run users keep picking up their old file).
    """
    if path is None:
        found = resolve_default_config_path()
        if found is None:
            return AuthSetting()
        return parse_setting_text(found.read_text(encoding="utf-8"), source=str(found))

    config_path = Path(path).expanduser()
    if config_path.exists():
        return parse_setting_text(config_path.read_text(encoding="utf-8"), source=str(config_path))
    if config_path == default_config_path() and LEGACY_CONFIG_PATH.exists():
        return parse_setting_text(
            LEGACY_CONFIG_PATH.read_text(encoding="utf-8"),
            source=str(LEGACY_CONFIG_PATH),
        )
    return AuthSetting()
