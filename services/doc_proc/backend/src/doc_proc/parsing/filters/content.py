"""Content noise filter for parsed elements.

Classifies each element as valuable/ambiguous/noise using weighted regex scoring.
Uses weighted domain patterns to remove common document noise.
"""

from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass
class ContentClassification:
    label: str  # "valuable" | "ambiguous" | "noise"
    confidence: float
    reason: str


# Noise patterns (to remove)
NOISE_PATTERNS: list[tuple[re.Pattern, str, float]] = [
    (re.compile(r"(?:\+7|8)\s*\(?\d{3}\)?[\s\-]*\d{3}[\s\-]*\d{2}[\s\-]*\d{2}"), "phone", 2.0),
    (re.compile(r"(?:г\.|ул\.|д\.|офис|корп|стр\.|пр-т|пер\.)", re.IGNORECASE), "address", 2.0),
    (re.compile(r"https?://|www\.|@\w+\.\w+", re.IGNORECASE), "url", 1.5),
    (re.compile(r"(?:ООО|ОАО|ЗАО|ПАО|АО|ИП|ИНН|ОГРН|КПП)", re.IGNORECASE), "legal", 2.0),
    (re.compile(r"(?:скидк|акци|распродаж|бесплатн|звоните)", re.IGNORECASE), "marketing", 1.5),
    (re.compile(r"\.{5,}|содержание|оглавление", re.IGNORECASE), "toc", 1.0),
    (re.compile(r"©|copyright|все права", re.IGNORECASE), "copyright", 1.5),
    (re.compile(r"^\s*\d{1,3}\s*$"), "page_number", 1.0),
]

# Valuable patterns (to keep)
VALUABLE_PATTERNS: list[tuple[re.Pattern, str, float]] = [
    (re.compile(r"[А-ЯA-Z]{2,}\d*[-\s]?\d+[хxХX×]\d+", re.IGNORECASE), "article_code", 2.0),
    (
        re.compile(
            r"\d+[\.,]?\d*\s*(?:мм²?|кВА?|IP\d{2}|°[CС]|кВт|А|В|Ом|кг|м[²³]?)",
            re.IGNORECASE,
        ),
        "spec_value",
        2.0,
    ),
    (
        re.compile(
            r"(?:кабель|провод|контактор|автомат|выключател|трансформатор|"
            r"УЗО|АВДТ|стабилизатор|щит)",
            re.IGNORECASE,
        ),
        "product_name",
        2.0,
    ),
    (re.compile(r"ГОСТ\s*[\d\.]+", re.IGNORECASE), "gost_ref", 1.5),
    (re.compile(r"[UIР]=\s*\d+", re.IGNORECASE), "rating", 1.5),
]


def classify_content(text: str) -> ContentClassification:
    """Classify a text element as valuable, ambiguous, or noise."""
    noise_score = 0.0
    value_score = 0.0
    noise_reasons: list[str] = []
    value_reasons: list[str] = []

    for pattern, category, weight in NOISE_PATTERNS:
        if pattern.search(text):
            noise_score += weight
            noise_reasons.append(category)

    for pattern, category, weight in VALUABLE_PATTERNS:
        if pattern.search(text):
            value_score += weight
            value_reasons.append(category)

    if value_score > noise_score:
        return ContentClassification(
            label="valuable",
            confidence=min(1.0, value_score / (value_score + noise_score + 0.1)),
            reason="+".join(value_reasons),
        )
    if noise_score > 0 and value_score == 0:
        return ContentClassification(
            label="noise",
            confidence=min(1.0, noise_score / (noise_score + 1.0)),
            reason="+".join(noise_reasons),
        )
    return ContentClassification(
        label="ambiguous",
        confidence=0.5,
        reason="mixed" if noise_reasons else "unknown",
    )


def filter_elements(
    elements: list,
    *,
    include_ambiguous: bool = True,
) -> list:
    """Filter elements, removing noise. Section headers always kept."""
    result = []
    for el in elements:
        if getattr(el, "element_type", "") == "section_header":
            result.append(el)
            continue
        if getattr(el, "element_type", "") == "heading":
            result.append(el)
            continue

        cls = classify_content(el.text)
        if cls.label == "valuable":
            result.append(el)
        elif cls.label == "ambiguous" and include_ambiguous:
            result.append(el)
        # noise → skip
    return result
