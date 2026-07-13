"""CID garbage detection for PDF font-decoding artifacts.

pdfminer sometimes fails to decode fonts, producing (cid:123) sequences
instead of actual text. This filter detects and flags such content.
"""

from __future__ import annotations

from doc_proc.domain.patterns import CID_PATTERN


def is_cid_garbage(text: str) -> bool:
    """Detect pdfminer font-decoding garbage like (cid:123) sequences.

    Returns True if text contains >5 CID sequences occupying >15% of text length.
    """
    if len(text) < 50:
        return False
    matches = CID_PATTERN.findall(text)
    return len(matches) > 5 and len(matches) * 10 > len(text) * 0.15
