"""Built-in quality-gate selection."""

from __future__ import annotations

from doc_harvester.core import QualityGate
from doc_harvester.quality.basic import BasicQualityGate


def available_quality_gates() -> tuple[str, ...]:
    return ("basic",)


def create_quality_gate(name: str = "basic", **options) -> QualityGate:
    normalized = name.strip().lower()
    if normalized in {"basic", "default"}:
        return BasicQualityGate(**options)
    raise ValueError(
        f"unknown quality gate '{name}'; available quality gates: "
        f"{', '.join(available_quality_gates())}"
    )
