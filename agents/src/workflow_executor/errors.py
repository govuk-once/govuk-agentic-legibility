"""Exceptions raised by the server-driven journey executor."""


class JourneyExecutorError(RuntimeError):
    """Base exception for journey execution failures."""


class JourneyConfigurationError(JourneyExecutorError):
    """Raised when the journey service cannot be configured."""


class JourneyProtocolError(JourneyExecutorError):
    """Raised when the service returns an invalid or unsupported contract."""


class JourneyNotFoundError(JourneyExecutorError):
    """Raised when the requested journey is not advertised by the service."""


class JourneyHttpError(JourneyExecutorError):
    """Raised when the journey service returns a non-successful HTTP response."""
