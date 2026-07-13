"""Row quality grading for parsed elements.

Calculates a 0.0-1.0 quality score based on field presence, recognized units,
and construction codes.
"""

from __future__ import annotations

import re
from typing import Any

CODE_PATTERNS = [
    re.compile(r"\d{2}\.\d+\.\d+\.\d+-\d+"),      # КСР: 01.7.15.03-0042
    re.compile(r"\d{2}-\d{2}-\d{3}-\d+"),           # ГЭСН/ФЕР: 11-01-001-01
    re.compile(r"КП\s*№?\d+"),                       # Commercial proposal
    re.compile(r"\d{3}-\d{4}"),                       # 999-9950
]

UNIT_PATTERN = re.compile(
    r"(мм|mm|м2|м3|м|m|кг|kg|шт|pcs|т|компл|пог\.\s*м|п\.м|куб\.\s*м|"
    r"л|усл\.\s*ед|маш\.\s*час|чел\.\s*час|кВт|kW|МПа|Па|1000\s*шт)",
    re.IGNORECASE,
)

HIGH_VALUE_FIELDS = {"name", "code", "наименование", "обоснование", "шифр"}


def calculate_grade(attributes: dict[str, Any]) -> float:
    """Calculate normalization grade (0.0-1.0) for a parsed row."""
    if not attributes:
        return 0.0

    total_score = 0.0
    field_count = 0

    for key, value in attributes.items():
        if value is None:
            continue
        val_str = str(value).strip()
        if not val_str:
            continue

        field_count += 1
        field_score = 0.0

        # Key score (0.0-0.5)
        if key.lower() in HIGH_VALUE_FIELDS:
            field_score += 0.5
        elif key.startswith("col_") or key == "line":
            field_score += 0.1
        else:
            field_score += 0.4

        # Value score (0.0-0.5)
        field_score += 0.25  # non-empty base
        if any(c.isdigit() for c in val_str):
            field_score += 0.05
        if UNIT_PATTERN.search(val_str):
            field_score += 0.1
        if any(p.search(val_str) for p in CODE_PATTERNS):
            field_score += 0.1
        if len(val_str) > 5:
            field_score += 0.05

        total_score += field_score

    if field_count == 0:
        return 0.0
    return min(1.0, total_score / field_count)
