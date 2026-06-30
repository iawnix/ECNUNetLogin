"""Compatibility loader for auth_client-style setting files."""

from __future__ import annotations

import dataclasses
from pathlib import Path

from .errors import CliError


DEFAULT_CONFIG_PATH = Path.home() / ".auth-setting"


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
            raise CliError(f"invalid config line {source}:{line_no}: {raw_line!r}")
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
            raise CliError(f"invalid acid in {source}: {raw_acid!r}") from exc

    return AuthSetting(
        host=values.get("host", ""),
        acid=acid,
        campus_postfix=values.get("campus_postfix", ""),
        campus_url=values.get("campus_url", ""),
    )


def load_auth_setting(path: str | Path | None) -> AuthSetting:
    if not path:
        return AuthSetting()
    config_path = Path(path).expanduser()
    if not config_path.exists():
        return AuthSetting()
    return parse_setting_text(config_path.read_text(encoding="utf-8"), source=str(config_path))
