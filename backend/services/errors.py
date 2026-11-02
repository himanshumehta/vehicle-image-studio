"""Errors the services raise and the API maps to status codes. Messages are safe to show clients."""


class ModelUnavailableError(RuntimeError):
    """A model could not be loaded (missing weights or optional dependencies)."""


class ImageTooLargeError(ValueError):
    """The requested operation would exceed a configured size limit."""
