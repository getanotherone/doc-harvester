"""Provider- and domain-neutral chunk quality gate."""

from __future__ import annotations

import hashlib

from chunker import count_tokens
from doc_harvester.core import (
    Chunk,
    ExtractedDocument,
    QualityFinding,
    QualityGate,
    QualityReport,
)


class BasicQualityGate(QualityGate):
    """Evaluate empty, tiny, duplicate, noisy, and oversized chunk ratios."""

    name = "basic"

    def __init__(
        self,
        *,
        min_tokens: int = 20,
        max_empty_ratio: float = 0.0,
        max_tiny_ratio: float = 0.8,
        max_duplicate_ratio: float = 0.25,
        max_noisy_ratio: float = 0.1,
        max_oversized_ratio: float = 0.0,
    ) -> None:
        if min_tokens < 1:
            raise ValueError("quality minimum tokens must be at least 1")
        for name, value in (
            ("empty", max_empty_ratio),
            ("tiny", max_tiny_ratio),
            ("duplicate", max_duplicate_ratio),
            ("noisy", max_noisy_ratio),
            ("oversized", max_oversized_ratio),
        ):
            if not 0.0 <= value <= 1.0:
                raise ValueError(f"quality {name} ratio must be between 0 and 1")
        self.min_tokens = min_tokens
        self.thresholds = {
            "max_empty_ratio": max_empty_ratio,
            "max_tiny_ratio": max_tiny_ratio,
            "max_duplicate_ratio": max_duplicate_ratio,
            "max_noisy_ratio": max_noisy_ratio,
            "max_oversized_ratio": max_oversized_ratio,
        }

    def evaluate(
        self,
        document: ExtractedDocument,
        chunks: list[Chunk] | tuple[Chunk, ...],
    ) -> QualityReport:
        if not document.blocks or not chunks:
            return QualityReport(
                False,
                findings=(
                    QualityFinding(
                        "missing_content",
                        "error",
                        "document blocks and chunks are required",
                    ),
                ),
                metrics={
                    "total_chunks": len(chunks),
                    "thresholds": {"min_tokens": self.min_tokens, **self.thresholds},
                },
            )

        empty = tiny = noisy = oversized = 0
        hashes: dict[str, int] = {}
        token_counts: list[int] = []
        for chunk in chunks:
            text = chunk.text.strip()
            token_count = int(chunk.metadata.get("token_count") or count_tokens(text))
            token_counts.append(token_count)
            if not text:
                empty += 1
                continue
            if token_count < self.min_tokens:
                tiny += 1
            if self._is_noisy(text):
                noisy += 1
            if bool(chunk.metadata.get("oversized")):
                oversized += 1
            normalized = " ".join(text.split()).lower()
            digest = str(chunk.metadata.get("content_sha256") or "") or hashlib.sha256(
                normalized.encode("utf-8")
            ).hexdigest()
            hashes[digest] = hashes.get(digest, 0) + 1

        duplicate = sum(count - 1 for count in hashes.values() if count > 1)
        total = len(chunks)
        counts = {
            "empty_chunks": empty,
            "tiny_chunks": tiny,
            "duplicate_chunks": duplicate,
            "noisy_chunks": noisy,
            "oversized_chunks": oversized,
        }
        ratios = {
            "empty_ratio": self._ratio(empty, total),
            "tiny_ratio": self._ratio(tiny, total),
            "duplicate_ratio": self._ratio(duplicate, total),
            "noisy_ratio": self._ratio(noisy, total),
            "oversized_ratio": self._ratio(oversized, total),
        }
        findings = []
        for label, ratio in ratios.items():
            threshold_name = f"max_{label}"
            maximum = self.thresholds[threshold_name]
            if ratio > maximum:
                findings.append(
                    QualityFinding(
                        f"{label}_exceeded",
                        "warning",
                        f"{label.replace('_', ' ')} exceeds configured maximum",
                        metadata={"value": ratio, "maximum": maximum},
                    )
                )

        return QualityReport(
            not findings,
            findings=tuple(findings),
            metrics={
                "total_chunks": total,
                **counts,
                "average_token_count": round(sum(token_counts) / total, 2),
                "max_token_count": max(token_counts, default=0),
                "ratios": ratios,
                "thresholds": {"min_tokens": self.min_tokens, **self.thresholds},
            },
        )

    @staticmethod
    def _ratio(value: int, total: int) -> float:
        return value / total if total else 0.0

    @staticmethod
    def _is_noisy(text: str) -> bool:
        if text.count("(cid:") > 5:
            return True
        if len(text) < 200:
            return False
        if text.count("�") / len(text) > 0.02:
            return True
        pipe_lines = sum("|" in line for line in text.splitlines())
        if pipe_lines >= 2:
            return False
        alpha = sum(character.isalpha() for character in text)
        digits = sum(character.isdigit() for character in text)
        symbols = sum(
            not character.isalnum() and not character.isspace() for character in text
        )
        total = len(text)
        return alpha / total < 0.45 and (
            symbols / total > 0.18 or digits / total > 0.40
        )
