"""Credential-free built-in extraction adapters."""

from doc_harvester.extractors.factory import (
    available_extractors,
    create_extractor,
    select_extractor,
)
from doc_harvester.extractors.docx import DOCXExtractor
from doc_harvester.extractors.html import HTMLExtractor
from doc_harvester.extractors.pdf import PDFExtractor
from doc_harvester.extractors.text import TextExtractor
from doc_harvester.extractors.xlsx import XLSXExtractor

__all__ = [
    "DOCXExtractor",
    "HTMLExtractor",
    "PDFExtractor",
    "TextExtractor",
    "XLSXExtractor",
    "available_extractors",
    "create_extractor",
    "select_extractor",
]
