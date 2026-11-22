"""The errors the services can raise."""


class PermissionDenied(Exception):
    """The role is not allowed to do this."""


class NotFoundError(LookupError):
    """The record does not exist."""


class AuthError(Exception):
    """The login failed."""
