"""Domain metadata extraction for electrical engineering documents.

Extracts vendor, standard ID, doc type, language, year, and source type
from chunk text and document name. Ported from src/chunker.py _infer_stage3_metadata.
"""

from __future__ import annotations

import os
import re

from doc_proc.domain.patterns import (
    CATALOG_TOKENS,
    FIRE_TOKENS,
    NORMATIVE_TOKENS,
    STANDARD_ID_REGEX,
    VENDOR_PATTERNS,
    YEAR_REGEX,
)


def infer_metadata(
    text: str,
    *,
    document_name: str = "",
    section: str = "",
) -> dict[str, object]:
    """Extract domain metadata from chunk text.

    Args:
        text: Chunk text content.
        document_name: Original document filename.
        section: Section heading for additional context.

    Returns:
        Dict with keys: doc_type, vendor, standard_id, year, lang, source_type.
    """
    probe_text = f"{document_name}\n{section}\n{text[:2000]}"
    lowered = probe_text.lower()

    # Source type from file extension
    source_type = "unknown"
    doc_base = os.path.basename(document_name)
    _, ext = os.path.splitext(doc_base.lower())
    if ext in {".pdf", ".docx", ".xlsx", ".html", ".htm", ".xml"}:
        source_type = ext.lstrip(".")

    # Vendor detection
    vendor = ""
    for candidate, aliases in VENDOR_PATTERNS.items():
        if any(alias in lowered for alias in aliases):
            vendor = candidate
            break

    # Standard ID extraction
    standard_id = ""
    standard_match = STANDARD_ID_REGEX.search(probe_text)
    if standard_match:
        standard_id = re.sub(r"\s+", " ", standard_match.group(0)).strip(" .,:;")

    # Year extraction (prefer from standard ID, fallback to text)
    year = None
    year_source = standard_id if standard_id else probe_text
    year_match = YEAR_REGEX.search(year_source)
    if year_match:
        year = int(year_match.group(1))

    # Language detection via script analysis
    lang = detect_language(probe_text)

    # Doc type classification
    if any(token in lowered for token in FIRE_TOKENS):
        doc_type = "fire"
    elif standard_id or any(token in lowered for token in NORMATIVE_TOKENS):
        doc_type = "normative"
    elif vendor or any(token in lowered for token in CATALOG_TOKENS):
        doc_type = "catalog"
    else:
        doc_type = "technical"

    return {
        "doc_type": doc_type,
        "vendor": vendor,
        "standard_id": standard_id,
        "year": year,
        "lang": lang,
        "source_type": source_type,
    }


def detect_language(text: str) -> str:
    """Detect language based on Cyrillic vs Latin character ratio."""
    cyrillic_count = sum(1 for ch in text if "а" <= ch.lower() <= "я" or ch.lower() == "ё")
    latin_count = sum(1 for ch in text if "a" <= ch.lower() <= "z")
    if cyrillic_count and latin_count:
        return "mixed"
    elif cyrillic_count:
        return "ru"
    elif latin_count:
        return "en"
    return "unknown"
