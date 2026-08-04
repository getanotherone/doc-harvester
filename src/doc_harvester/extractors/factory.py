"""Built-in extractor selection."""

from __future__ import annotations

from doc_harvester.core import Extractor, FetchedArtifact
from doc_harvester.extractors.docx import DOCXExtractor
from doc_harvester.extractors.html import HTMLExtractor
from doc_harvester.extractors.pdf import PDFExtractor
from doc_harvester.extractors.text import TextExtractor
from doc_harvester.extractors.xlsx import XLSXExtractor


def available_extractors() -> tuple[str, ...]:
    return ("text", "html-xml", "pdf", "docx", "xlsx")


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
    if normalized == "xlsx":
        return XLSXExtractor()
    raise ValueError(
        f"unknown extractor '{name}'; available extractors: {', '.join(available_extractors())}"
    )


def select_extractor(
    artifact: FetchedArtifact,
    *,
    max_pdf_pages: int = 1000,
    max_docx_blocks: int = 10_000,
    max_docx_uncompressed_bytes: int = 100 * 1024 * 1024,
    max_xlsx_sheets: int = 100,
    max_xlsx_rows: int = 200_000,
    max_xlsx_cells: int = 2_000_000,
    max_xlsx_uncompressed_bytes: int = 250 * 1024 * 1024,
    include_hidden_xlsx_sheets: bool = False,
) -> Extractor | None:
    for extractor in (
        PDFExtractor(max_pages=max_pdf_pages),
        DOCXExtractor(
            max_blocks=max_docx_blocks,
            max_uncompressed_bytes=max_docx_uncompressed_bytes,
        ),
        XLSXExtractor(
            max_sheets=max_xlsx_sheets,
            max_rows=max_xlsx_rows,
            max_cells=max_xlsx_cells,
            max_uncompressed_bytes=max_xlsx_uncompressed_bytes,
            include_hidden_sheets=include_hidden_xlsx_sheets,
        ),
        HTMLExtractor(),
        TextExtractor(),
    ):
        if extractor.supports(artifact):
            return extractor
    return None
