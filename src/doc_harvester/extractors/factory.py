"""Built-in extractor selection."""

from __future__ import annotations

from doc_harvester.core import Extractor, FetchedArtifact
from doc_harvester.extractors.html import HTMLExtractor
from doc_harvester.extractors.text import TextExtractor


def available_extractors() -> tuple[str, ...]:
    return ("text", "html-xml")


def create_extractor(name: str) -> Extractor:
    normalized = name.strip().lower()
    if normalized == "text":
        return TextExtractor()
    if normalized in {"html", "html-xml", "xml"}:
        return HTMLExtractor()
    raise ValueError(
        f"unknown extractor '{name}'; available extractors: {', '.join(available_extractors())}"
    )


def select_extractor(artifact: FetchedArtifact) -> Extractor | None:
    for extractor in (HTMLExtractor(), TextExtractor()):
        if extractor.supports(artifact):
            return extractor
    return None

