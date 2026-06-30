"""HTTP boundary for SRun portal operations."""

from __future__ import annotations

import json
import sys
import urllib.error
import urllib.request
from typing import Any, Dict, Mapping

from .constants import DEFAULT_TIMEOUT, DEFAULT_USER_AGENT
from .errors import CliError
from .models import AuthParams, AuthResult, OnlineStatus, SrunUrlProvider
from .protocol import (
    add_auth_callback,
    build_challenge_params,
    build_request_params,
    find_acid,
    find_json,
    query_string,
)


class SrunClient:
    def __init__(
        self,
        provider: SrunUrlProvider,
        *,
        timeout: float = DEFAULT_TIMEOUT,
        debug: bool = False,
        user_agent: str = DEFAULT_USER_AGENT,
    ) -> None:
        if timeout <= 0:
            raise CliError("--timeout must be positive")
        self.provider = provider
        self.timeout = timeout
        self.debug = debug
        self.user_agent = user_agent

    def fetch_acid(self) -> int:
        html = self.get_text(self.provider.index())
        return find_acid(html)

    def fetch_token(self, username: str, ip: str) -> str:
        body = self.get_text(
            self.provider.challenge(),
            build_challenge_params(username=username, ip=ip),
        )
        data = decode_jsonp_or_json(body)
        token = data.get("challenge")
        if not isinstance(token, str) or not token:
            raise CliError(f"challenge token not found in response: {body!r}")
        return token

    def build_auth_request(
        self,
        *,
        username: str,
        password: str,
        action: str,
        ip: str,
        acid: int | None = None,
        token: str | None = None,
        include_callback: bool = True,
    ) -> Dict[str, str]:
        resolved_acid = self.fetch_acid() if acid is None else acid
        resolved_token = self.fetch_token(username, ip) if token is None else token
        request = build_request_params(
            AuthParams(
                username=username,
                password=password,
                token=resolved_token,
                action=action,
                ip=ip,
                acid=resolved_acid,
            )
        )
        return add_auth_callback(request) if include_callback else request

    def submit_auth(self, request: Mapping[str, str]) -> AuthResult:
        body = self.get_text(self.provider.auth(), request)
        return AuthResult(request=dict(request), body=body)

    def check_online_status(self) -> OnlineStatus:
        body = self.get_text(self.provider.check()).strip()
        if "not_online_error" in body:
            return OnlineStatus(online=False, raw=body)
        username = body.split(",", 1)[0].strip()
        return OnlineStatus(online=bool(username), username=username, raw=body)

    def get_text(self, url: str, params: Mapping[str, str] | None = None) -> str:
        return get_text(
            url,
            params,
            timeout=self.timeout,
            debug=self.debug,
            user_agent=self.user_agent,
        )


def get_text(
    url: str,
    params: Mapping[str, str] | None = None,
    timeout: float = DEFAULT_TIMEOUT,
    debug: bool = False,
    user_agent: str = DEFAULT_USER_AGENT,
) -> str:
    """One-shot HTTP GET helper."""

    if params:
        url = f"{url}?{query_string(params)}"
    if debug:
        print(f"GET {url}", file=sys.stderr)
    req = urllib.request.Request(url, headers={"User-Agent": user_agent})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.read().decode("utf-8", errors="replace")
    except urllib.error.URLError as exc:
        reason = getattr(exc, "reason", exc)
        raise CliError(f"request failed for {url}: {reason}") from exc


def decode_jsonp_or_json(text: str) -> Dict[str, Any]:
    try:
        payload = find_json(text)
    except ValueError:
        payload = text
    data = json.loads(payload)
    if not isinstance(data, dict):
        raise CliError(f"expected JSON object, got {type(data).__name__}")
    return data


def auto_fetch_acid(provider: SrunUrlProvider, timeout: float, debug: bool) -> int:
    return SrunClient(provider, timeout=timeout, debug=debug).fetch_acid()


def auto_fetch_token(
    provider: SrunUrlProvider,
    username: str,
    ip: str,
    timeout: float,
    debug: bool,
) -> str:
    return SrunClient(provider, timeout=timeout, debug=debug).fetch_token(username, ip)


def check_online_status(
    provider: SrunUrlProvider,
    timeout: float = DEFAULT_TIMEOUT,
    debug: bool = False,
) -> OnlineStatus:
    return SrunClient(provider, timeout=timeout, debug=debug).check_online_status()
