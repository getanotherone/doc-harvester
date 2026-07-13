"""Chunk-level filters — metadata skip, OCR garbage, pattern filters."""

from __future__ import annotations

import re

from doc_proc.domain.cid_filter import is_cid_garbage as _is_cid_garbage
from doc_proc.models import RawChunk

# Metadata row detection patterns (construction document noise)
METADATA_PATTERNS = [
    re.compile(r"(?:ИНН|ОГРН|КПП|БИК)\s*:?\s*\d", re.IGNORECASE),
    re.compile(r"(?:ООО|ОАО|ЗАО|ПАО|АО)\s+[«\"]", re.IGNORECASE),
    re.compile(r"(?:ИТОГО|ВСЕГО|итого)\s*(?:по|:|\s*$)", re.IGNORECASE),
    re.compile(r"(?:тел|факс|телефон|e-?mail)\s*[:/]", re.IGNORECASE),
    re.compile(r"(?:подпись|дата|М\.П\.|печать)", re.IGNORECASE),
]

METADATA_KEYWORDS = frozenset({
    "итого", "всего", "подитог", "субподряд",
    "заказчик", "подрядчик", "исполнитель",
    "генподрядчик", "субподрядчик",
})

# Office/contact block detection — catalog boilerplate at start/end of docs
OFFICE_PATTERNS = [
    re.compile(r"(?:ОФИС В|офис в)\s+[А-ЯA-Z]", re.IGNORECASE),
    re.compile(
        r"(?:ЛАТВИЯ|УЗБЕКИСТАН|МОНГОЛИЯ|ГРУЗИЯ|КАЗАХСТАН|БЕЛАРУСЬ|МОЛДОВА|КЫРГЫЗСТАН)"
        r".*(?:тел|tel|факс|fax|@)",
        re.IGNORECASE | re.DOTALL,
    ),
]


def is_office_boilerplate(text: str) -> bool:
    """Check if text is office/contact boilerplate from catalog pages."""
    return any(p.search(text) for p in OFFICE_PATTERNS)


def is_metadata_row(text: str) -> bool:
    """Check if text is a metadata/administrative row."""
    lower = text.lower().strip()
    if any(kw in lower for kw in METADATA_KEYWORDS):
        return True
    return any(p.search(text) for p in METADATA_PATTERNS)


def is_ocr_garbage(text: str, min_alpha_ratio: float = 0.4) -> bool:
    """Check if text is OCR garbage (low alphanumeric ratio)."""
    if len(text) < 20:
        return False  # Too short to judge
    alnum_count = sum(1 for c in text if c.isalnum())
    return (alnum_count / len(text)) < min_alpha_ratio


def apply_filters(
    chunks: list[RawChunk],
    *,
    min_text_length: int = 20,
    skip_metadata: bool = True,
    skip_ocr_garbage: bool = True,
    skip_cid_garbage: bool = True,
    skip_office_boilerplate: bool = True,
    exclude_patterns: list[str] | None = None,
    include_patterns: list[str] | None = None,
) -> list[RawChunk]:
    """Apply filter chain to chunks.

    Filters applied in order:
    1. skip_metadata — remove administrative/metadata rows
    2. min_text_length — discard short chunks
    3. skip_ocr_garbage — remove OCR artifacts
    3b. skip_cid_garbage — remove PDF font-decoding artifacts (cid:NNN)
    3c. skip_office_boilerplate — remove catalog office/contact pages
    4. exclude_patterns / include_patterns — regex filtering
    """
    result: list[RawChunk] = []

    compiled_exclude = [re.compile(p, re.IGNORECASE) for p in (exclude_patterns or [])]
    compiled_include = [re.compile(p, re.IGNORECASE) for p in (include_patterns or [])]

    for chunk in chunks:
        text = chunk.text.strip()

        # Always keep headings
        if chunk.chunk_type == "heading":
            result.append(chunk)
            continue

        # 1. Metadata filter
        if skip_metadata and is_metadata_row(text):
            continue

        # 2. Minimum length
        if len(text) < min_text_length:
            continue

        # 3. OCR garbage
        if skip_ocr_garbage and is_ocr_garbage(text):
            continue

        # 3b. CID garbage (PDF font-decoding artifacts)
        if skip_cid_garbage and _is_cid_garbage(text):
            continue

        # 3c. Office/contact boilerplate (catalog pages)
        if skip_office_boilerplate and is_office_boilerplate(text):
            continue

        # 4. Exclude patterns
        if compiled_exclude and any(p.search(text) for p in compiled_exclude):
            continue

        # 5. Include patterns (if specified, only keep matching)
        if compiled_include and not any(p.search(text) for p in compiled_include):
            continue

        result.append(chunk)

    return result
