"""Error types used by the auth_ecnu CLI and client."""


class AuthEcnuError(Exception):
    """Base user-facing runtime error."""


class CliError(AuthEcnuError):
    """User-facing CLI/runtime error."""
