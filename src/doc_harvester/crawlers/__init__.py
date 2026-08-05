"""Credential-free built-in crawler adapters."""

from doc_harvester.crawlers.factory import available_crawlers, create_crawler
from doc_harvester.crawlers.html import HTMLCrawler

__all__ = ["HTMLCrawler", "available_crawlers", "create_crawler"]
