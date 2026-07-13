"""Regex patterns and constants for electrical engineering document processing.

Ported from spec_scraper src/chunker.py — battle-tested on 337K chunks.
"""

from __future__ import annotations

import re

# Normative block detection (numbered paragraphs: 1.2.3, a), I.)
NORMATIVE_PATTERN = re.compile(
    r"^\s*((\d+(\.\d+){0,4})|([A-Za-zА-Яа-я]\))|([IVXLCMivxlcm]+\.))\s+"
)

# Section/heading patterns
SECTION_PATTERN = re.compile(
    r"^\s*((Раздел|Section|Глава)\s+\d+|\d+(\.\d+)*\s+[A-Za-zА-Яа-я])"
)
NUMBERED_HEADING_PATTERN = re.compile(r"^\s*(\d+(?:\.\d+){0,4})\s+(.+)$")

# Table detection helpers
CODE_LINE_PATTERN = re.compile(r"^[A-ZА-ЯЁ]{1,4}[-\s]?\d{2,6}([-/][A-ZА-ЯЁ0-9]+)?$")
NUMERIC_HEAVY_PATTERN = re.compile(r"^[\d\s.,xXхХ\-–+/%°\"']+$")
TABLE_HINT_WORDS = (
    "артикул",
    "внутренние размеры",
    "внешние размеры",
    "размер ниши",
    "количество в упаковке",
    "шт.",
    "мм",
    "d1",
    "d2",
    "b1",
    "b2",
)

# Standard ID extraction (ГОСТ, СП, IEC, ISO, etc.)
STANDARD_ID_REGEX = re.compile(
    r"(?:ГОСТ(?:\s+Р)?|GOST(?:\s+R)?|СНиП|SNIP|IEC|ISO)"
    r"\s*\d[\d.\-/–— ]{0,25}\d"
    r"|\b(?:СП|ФЗ)\s+\d[\d.\-/–— ]{0,25}\d",
    re.IGNORECASE,
)

# Year extraction
YEAR_REGEX = re.compile(r"\b(19\d{2}|20[0-3]\d)\b")

# CID garbage (pdfminer font-decoding artifacts)
CID_PATTERN = re.compile(r"\(cid:\d+\)")

# Vendor patterns: canonical name → lowercase aliases
VENDOR_PATTERNS: dict[str, tuple[str, ...]] = {
    "ABB": ("abb",),
    "Schneider": ("schneider", "se ", "шнайдер"),
    "Legrand": ("legrand", "легран"),
    "IEK": ("iek", "иэк"),
    "EKF": ("ekf",),
    "Hager": ("hager",),
    "DKC": ("dkc", "дкс"),
}

# Doc type classification keywords
FIRE_TOKENS = ("пожар", "огнестой", "пожарн", "fire", "flame")
NORMATIVE_TOKENS = ("гост", "сп ", "снип", "пуэ", "пэу", "норматив", "стандарт", "regulation")
CATALOG_TOKENS = ("каталог", "catalog", "datasheet", "технический каталог")
