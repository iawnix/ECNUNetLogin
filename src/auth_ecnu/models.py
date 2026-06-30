"""Typed data models for SRun requests."""

from __future__ import annotations

import dataclasses
import urllib.parse
from typing import Dict

from .errors import CliError


@dataclasses.dataclass(frozen=True)
class SrunUrlProvider:
    protocol: str
    host: str

    def index(self) -> str:
        return f"{self.protocol}://{self.host}"

    def challenge(self) -> str:
        return f"{self.index()}/cgi-bin/get_challenge"

    def auth(self) -> str:
        return f"{self.index()}/cgi-bin/srun_portal"

    def check(self) -> str:
        return f"{self.index()}/cgi-bin/rad_user_info"

    @classmethod
    def from_host(cls, host: str) -> "SrunUrlProvider":
        parsed = urllib.parse.urlparse(host if "://" in host else f"http://{host}")
        if not parsed.hostname:
            raise CliError(f"invalid host: {host!r}")
        if parsed.scheme not in {"http", "https"}:
            raise CliError(f"unsupported URL scheme: {parsed.scheme!r}")
        return cls(protocol=parsed.scheme or "http", host=parsed.netloc)


@dataclasses.dataclass(frozen=True)
class AuthParams:
    username: str
    password: str
    token: str
    action: str
    ip: str
    acid: int

    def __post_init__(self) -> None:
        if self.action not in {"login", "logout"}:
            raise ValueError("action must be login or logout")
        if self.action == "login" and not self.password:
            raise ValueError("password is required for login")
        if not self.username:
            raise ValueError("username is required")
        if not self.token:
            raise ValueError("challenge token is required")
        if self.acid < 0:
            raise ValueError("acid must be zero or positive")


@dataclasses.dataclass(frozen=True)
class OnlineStatus:
    online: bool
    username: str = ""
    raw: str = ""


@dataclasses.dataclass(frozen=True)
class AuthResult:
    request: Dict[str, str]
    body: str
