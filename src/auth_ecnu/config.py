"""Loader for the auth_ecnu setting file.

The default config location follows the XDG Base Directory specification on
Linux/macOS and uses ``%APPDATA%`` on Windows.

**Security**: the setting file is for portal-side identifiers only —
``host``, ``acid``, ``campus_postfix``, ``campus_url``. **Never** put a
username or a password here. Unknown keys are silently ignored, so a
legacy file containing ``username=…`` will not break but also will not
populate any field; pass ``--username``/``-u`` (or use ``--in-json``)
explicitly each time.
"""

from __future__ import annotations

import dataclasses
import os
import sys
from pathlib import Path

from .errors import UsageError


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


@dataclasses.dataclass(frozen=True)
class AuthSetting:
    host: str = ""
    acid: int | None = None
    campus_postfix: str = ""
    campus_url: str = ""


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

    # Unknown keys (e.g. legacy ``username``) are silently dropped — see
    # the module docstring for why credentials must not live in this file.
    return AuthSetting(
        host=values.get("host", ""),
        acid=acid,
        campus_postfix=values.get("campus_postfix", ""),
        campus_url=values.get("campus_url", ""),
    )


def load_auth_setting(path: str | Path | None) -> AuthSetting:
    """Load an auth-setting file.

    - ``None`` reads :func:`default_config_path` if it exists.
    - An explicit path is read when present; missing paths silently
      return defaults (matching the "no config, no problem" UX).
    """
    config_path = Path(path).expanduser() if path else default_config_path()
    if not config_path.exists():
        return AuthSetting()
    return parse_setting_text(config_path.read_text(encoding="utf-8"), source=str(config_path))
