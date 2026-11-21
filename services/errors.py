"""Errors raised by the service layer."""


class PermissionDenied(Exception):
    """The user's role does not allow this action."""


class NotFoundError(LookupError):
    """The record does not exist."""


class AuthError(Exception):
    """Login failed."""
