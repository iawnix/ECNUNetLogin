"""ECNU/SRun auth_client Python refactor."""

from .client import SrunClient, auto_fetch_acid, auto_fetch_token, check_online_status, decode_jsonp_or_json, get_text
from .models import AuthParams, AuthResult, OnlineStatus, SrunUrlProvider
from .protocol import (
    add_auth_callback,
    build_challenge_params,
    build_request_params,
    find_acid,
    find_json,
    online_status_to_dict,
    query_string,
    quirk_base64_encode,
    sha1sum,
    xencode,
)

__all__ = [
    "AuthParams",
    "AuthResult",
    "OnlineStatus",
    "SrunClient",
    "SrunUrlProvider",
    "add_auth_callback",
    "auto_fetch_acid",
    "auto_fetch_token",
    "build_challenge_params",
    "build_request_params",
    "check_online_status",
    "decode_jsonp_or_json",
    "find_acid",
    "find_json",
    "get_text",
    "online_status_to_dict",
    "query_string",
    "quirk_base64_encode",
    "sha1sum",
    "xencode",
]
