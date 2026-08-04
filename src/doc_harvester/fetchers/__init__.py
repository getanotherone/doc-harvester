"""Credential-free built-in fetcher adapters."""

from doc_harvester.fetchers.errors import FetchError, FetchTooLargeError, UnsupportedSchemeError
from doc_harvester.fetchers.factory import available_fetchers, create_fetcher
from doc_harvester.fetchers.http import HTTPFetcher
from doc_harvester.fetchers.local import LocalFileFetcher

__all__ = [
    "FetchError",
    "FetchTooLargeError",
    "HTTPFetcher",
    "LocalFileFetcher",
    "UnsupportedSchemeError",
    "available_fetchers",
    "create_fetcher",
]
