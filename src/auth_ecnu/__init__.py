"""ECNU/SRun auth_client Python refactor."""

__version__ = "0.4.0"

from .client import SrunClient, auto_fetch_acid, auto_fetch_token, check_online_status, decode_jsonp_or_json, get_text
from .config import AuthSetting, load_auth_setting, parse_setting_text
from .errors import AuthEcnuError, CliError, NetworkError, PortalError, UsageError
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
    "__version__",
    "AuthEcnuError",
    "AuthParams",
    "AuthResult",
    "AuthSetting",
    "CliError",
    "NetworkError",
    "OnlineStatus",
    "PortalError",
    "SrunClient",
    "SrunUrlProvider",
    "UsageError",
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
    "load_auth_setting",
    "online_status_to_dict",
    "parse_setting_text",
    "query_string",
    "quirk_base64_encode",
    "sha1sum",
    "xencode",
]
