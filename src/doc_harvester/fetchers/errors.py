"""Fetcher errors with provider-neutral, log-safe messages."""


class FetchError(RuntimeError):
    """Raised when a resource cannot be fetched safely."""


class FetchTooLargeError(FetchError):
    """Raised when a resource exceeds the configured byte limit."""


class UnsupportedSchemeError(FetchError):
    """Raised when a fetcher receives a resource it does not support."""
