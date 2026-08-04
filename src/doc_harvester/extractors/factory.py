"""Built-in extractor selection."""

from __future__ import annotations

from doc_harvester.core import Extractor, FetchedArtifact
from doc_harvester.extractors.docx import DOCXExtractor
from doc_harvester.extractors.html import HTMLExtractor
from doc_harvester.extractors.pdf import PDFExtractor
from doc_harvester.extractors.text import TextExtractor


def available_extractors() -> tuple[str, ...]:
    return ("text", "html-xml", "pdf", "docx")


def create_extractor(name: str) -> Extractor:
    normalized = name.strip().lower()
    if normalized == "text":
        return TextExtractor()
    if normalized in {"html", "html-xml", "xml"}:
        return HTMLExtractor()
    if normalized == "pdf":
        return PDFExtractor()
    if normalized == "docx":
        return DOCXExtractor()
    raise ValueError(
        f"unknown extractor '{name}'; available extractors: {', '.join(available_extractors())}"
    )


def select_extractor(
    artifact: FetchedArtifact,
    *,
    max_pdf_pages: int = 1000,
    max_docx_blocks: int = 10_000,
    max_docx_uncompressed_bytes: int = 100 * 1024 * 1024,
) -> Extractor | None:
    for extractor in (
        PDFExtractor(max_pages=max_pdf_pages),
        DOCXExtractor(
            max_blocks=max_docx_blocks,
            max_uncompressed_bytes=max_docx_uncompressed_bytes,
        ),
        HTMLExtractor(),
        TextExtractor(),
    ):
        if extractor.supports(artifact):
            return extractor
    return None
