"""Error types and exit codes used by the auth_ecnu CLI and client.

Exit code convention (mirrors common Unix tooling):

- 0  success
- 2  usage error: bad/missing CLI input or invalid config
- 3  network error: portal unreachable, timeout, DNS, TLS, etc.
- 4  portal error: portal reachable but returned an unexpected payload
"""


EXIT_OK = 0
EXIT_USAGE = 2
EXIT_NETWORK = 3
EXIT_PORTAL = 4


class AuthEcnuError(Exception):
    """Base user-facing runtime error."""

    exit_code: int = 1
    code: str = "error"


class CliError(AuthEcnuError):
    """Generic user-facing error (kept for backwards compat)."""

    exit_code = 1
    code = "error"


class UsageError(CliError):
    """Invalid CLI input, missing required options, or bad config."""

    exit_code = EXIT_USAGE
    code = "usage_error"


class NetworkError(CliError):
    """Portal unreachable or HTTP-layer failure."""

    exit_code = EXIT_NETWORK
    code = "network_error"


class PortalError(CliError):
    """Portal reachable but response was malformed or unexpected."""

    exit_code = EXIT_PORTAL
    code = "portal_error"
