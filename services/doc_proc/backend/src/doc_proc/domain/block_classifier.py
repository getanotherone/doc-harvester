"""Block type classification: table, normative, or normal text.

Ported from doc_harvester src/chunker.py — heuristic-based detection
of tabular data and normative (numbered) paragraphs.
"""

from __future__ import annotations

import re

from doc_proc.domain.patterns import (
    CODE_LINE_PATTERN,
    NORMATIVE_PATTERN,
    NUMERIC_HEAVY_PATTERN,
    TABLE_HINT_WORDS,
)


def is_table_like(text: str) -> bool:
    """Detect tabular content using pipe/tab/column-space heuristics."""
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if len(lines) < 2:
        return False

    pipe_lines = sum(1 for line in lines if "|" in line)
    tab_lines = sum(1 for line in lines if "\t" in line)
    col_space_lines = sum(1 for line in lines if re.search(r"\S\s{2,}\S", line))

    if pipe_lines >= 2 or tab_lines >= 2:
        return True
    if col_space_lines >= 3 and len(lines) >= 4:
        return True

    lowered = text.lower()
    generic_table_words = ["наименование", "ед.", "кол-во", "qty", "unit", "amount"]
    if any(word in lowered for word in generic_table_words) and col_space_lines >= 2:
        return True

    table_hint_hits = sum(1 for word in TABLE_HINT_WORDS if word in lowered)
    code_lines = sum(1 for line in lines if CODE_LINE_PATTERN.match(line))
    numeric_lines = sum(
        1
        for line in lines
        if any(ch.isdigit() for ch in line)
        and (NUMERIC_HEAVY_PATTERN.match(line) or len(line.split()) <= 3)
    )
    short_lines = sum(1 for line in lines if len(line) <= 18)

    if table_hint_hits >= 1 and (numeric_lines >= 3 or code_lines >= 2):
        return True
    if code_lines >= 3 and numeric_lines >= 3:
        return True
    if len(lines) >= 8 and short_lines / len(lines) >= 0.65 and (code_lines + numeric_lines) >= 5:
        return True

    return False


def is_normative_block(text: str) -> bool:
    """Detect normative (numbered) paragraphs like 1.2.3, a), I."""
    first_line = text.splitlines()[0].strip() if text.strip() else ""
    return bool(NORMATIVE_PATTERN.match(first_line))


def classify_block(text: str) -> list[str]:
    """Classify text block as table, normative, normal, or combination.

    Returns list of labels (a block can be both table and normative).
    """
    labels: list[str] = []
    if is_table_like(text):
        labels.append("table")
    if is_normative_block(text):
        labels.append("normative")
    if not labels:
        labels.append("normal")
    return labels
