"""Format detection and routing to the appropriate parser."""

from __future__ import annotations

import logging
import os
import re

from doc_proc.models import ParseResult

logger = logging.getLogger(__name__)

# Zero-width characters to strip from parsed text
_INVISIBLE_CHARS = re.compile(r"[\ufeff\u200b\u200c\u200d\u2060\ufffe]")

SUPPORTED_EXTENSIONS = {"csv", "xlsx", "xls", "pdf", "docx", "pptx"}


def detect_format(filename: str) -> str:
    """Detect file format from extension."""
    ext = os.path.splitext(filename)[1].lower().lstrip(".")
    if ext not in SUPPORTED_EXTENSIONS:
        raise ValueError(f"Unsupported file format: .{ext}")
    return ext


def parse_document(
    content: bytes,
    filename: str,
    *,
    force_docling: bool = False,
    ocr_engine: str = "tesseract",
    ocr_languages: str = "rus+eng",
    max_pdf_ocr_size_mb: int = 50,
) -> ParseResult:
    """Route document to appropriate parser and return ParseResult.

    Routing logic:
    - xlsx/xls/csv → ExcelParser (openpyxl streaming)
    - pdf (not force_docling) → try PdfTextParser first, fallback to PdfOcrParser
    - pdf (force_docling) → PdfOcrParser directly
    - docx/pptx → DocxParser (Docling)
    """
    ext = detect_format(filename)

    if ext in ("xlsx", "xls", "csv"):
        from doc_proc.parsing.excel import ExcelParser

        parser = ExcelParser()
        result = _cleanup_parsed_text(parser.parse(content, filename))
        logger.info(
            "Parsed %s: %d elements, format=%s",
            filename, len(result.elements), result.format_hint,
        )
        return result

    if ext == "pdf":
        if not force_docling:
            from doc_proc.parsing.pdf_text import PdfTextParser

            text_parser = PdfTextParser()
            if text_parser.is_text_based(content):
                result = _cleanup_parsed_text(text_parser.parse(content, filename))
                logger.info(
                    "Parsed %s (text PDF): %d elements", filename, len(result.elements)
                )
                return result

            # Check size limit for OCR
            size_mb = len(content) / (1024 * 1024)
            if size_mb > max_pdf_ocr_size_mb:
                # Try text extraction anyway
                result = text_parser.parse(content, filename)
                result = _cleanup_parsed_text(result)
                if result.elements:
                    logger.info(
                        "Parsed %s (large PDF, text-only): %d elements",
                        filename, len(result.elements),
                    )
                    return result
                raise ValueError(
                    f"PDF too large for OCR ({size_mb:.1f} MB > {max_pdf_ocr_size_mb} MB) "
                    "and no extractable text found"
                )

        # Fall through to Docling/OCR
        from doc_proc.parsing.pdf_ocr import PdfOcrParser

        ocr_parser = PdfOcrParser(
            ocr_engine=ocr_engine,
            ocr_languages=ocr_languages,
        )
        result = _cleanup_parsed_text(ocr_parser.parse(content, filename))
        logger.info(
            "Parsed %s (OCR PDF): %d elements, pages=%d",
            filename, len(result.elements), result.page_count,
        )
        return result

    if ext in ("docx", "pptx"):
        from doc_proc.parsing.docx import DocxParser

        parser = DocxParser()
        result = _cleanup_parsed_text(parser.parse(content, filename))
        logger.info("Parsed %s: %d elements", filename, len(result.elements))
        return result

    raise ValueError(f"No parser available for .{ext}")


def _cleanup_parsed_text(result: ParseResult) -> ParseResult:
    """Post-parse text cleanup: BOM removal, reversed text detection."""
    for el in result.elements:
        # Strip BOM and zero-width characters
        el.text = _INVISIBLE_CHARS.sub("", el.text)

        # Detect reversed text (pdfplumber reading mirrored styled text)
        if el.text.strip() and _is_reversed_text(el.text):
            el.text = el.text[::-1]

        # Clean section too
        if el.section:
            el.section = _INVISIBLE_CHARS.sub("", el.section)
            if _is_reversed_text(el.section):
                el.section = el.section[::-1]

    return result


def _is_reversed_text(text: str) -> bool:
    """Detect if text is reversed (mirrored PDF rendering).

    Heuristic: Russian text ending with uppercase letter patterns that
    don't form valid words, but reversed text does.
    """
    stripped = text.strip()
    if len(stripped) < 5:
        return False

    # Only check Cyrillic text
    cyrillic = sum(1 for c in stripped if "\u0400" <= c <= "\u04ff")
    if cyrillic < len(stripped) * 0.5:
        return False

    # Check if reversing produces more recognizable Russian word patterns
    # Common Russian word endings that appear at start when reversed
    reversed_markers = (
        "яансап", "яачобар", "еиксеч", "еыньлет", "яинедев",
        "еоньлау", "ЕИКСЕЧ", "ЕЫНЬЛЕТ", "ЯАНСАП",
    )
    # Common Russian word beginnings
    normal_markers = (
        "безопас", "рабоча", "техниче", "дополнит", "введени",
        "удальн", "БЕЗОПАС", "ТЕХНИЧЕ", "ДОПОЛНИТ",
    )

    has_reversed = any(stripped.startswith(m) for m in reversed_markers)
    has_normal = any(stripped.startswith(m) for m in normal_markers)

    if has_reversed and not has_normal:
        return True

    return False
