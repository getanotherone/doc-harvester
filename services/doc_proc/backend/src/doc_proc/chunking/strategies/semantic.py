"""Semantic chunking — regex pattern splitting for construction documents.

Uses domain-specific patterns (Smeta sections, spec items, КСР codes)
to find natural split points in document text.
"""

from __future__ import annotations

import re

from doc_proc.chunking.splitters import split_text
from doc_proc.models import ChunkResult, ParseResult, RawChunk, estimate_tokens

CONSTRUCTION_SPLIT_PATTERNS = {
    "smeta_section": re.compile(
        r"(?=^(?:Раздел|Глава|Часть|РАЗДЕЛ|ГЛАВА)\s+)",
        re.MULTILINE,
    ),
    "spec_item": re.compile(
        r"(?=^(?:Поз(?:иция)?|Позиция)\s*[\.\)№]\s*\d+)",
        re.MULTILINE,
    ),
    "ksr_code": re.compile(
        r"(?=^\d{2}-\d{2}-\d{3}-\d{2})",
        re.MULTILINE,
    ),
    "numbered_item": re.compile(
        r"(?=^\d{1,3}[\.\)]\s+[А-ЯA-Z])",
        re.MULTILINE,
    ),
    "bom_group": re.compile(
        r"(?=^(?:Группа|Категория|Подкатегория|ГРУППА)\s+)",
        re.MULTILINE,
    ),
}

MIN_PARTS = 3  # Require at least 3 parts to use a pattern


class SemanticChunker:
    """Pattern-based semantic splitter for construction documents."""

    name = "semantic"

    def chunk(
        self,
        parse_result: ParseResult,
        *,
        max_tokens: int = 512,
        **kwargs,
    ) -> ChunkResult:
        elements = [el for el in parse_result.elements if el.text.strip()]
        if not elements:
            return ChunkResult(chunks=[], strategy_used=self.name)

        # Build text-to-element mapping for page/section recovery
        full_text = "\n".join(el.text for el in elements)
        # Track cumulative char offsets for each element
        element_offsets: list[tuple[int, int]] = []  # (start, end) in full_text
        pos = 0
        for el in elements:
            start = pos
            end = pos + len(el.text)
            element_offsets.append((start, end))
            pos = end + 1  # +1 for the \n join

        # Try each pattern in priority order
        for pattern_name, pattern in CONSTRUCTION_SPLIT_PATTERNS.items():
            parts = pattern.split(full_text)
            parts = [p.strip() for p in parts if p.strip()]

            if len(parts) >= MIN_PARTS:
                chunks = self._parts_to_chunks_with_metadata(
                    parts, max_tokens, full_text, elements, element_offsets
                )
                return ChunkResult(
                    chunks=chunks,
                    strategy_used=self.name,
                    stats={
                        "pattern_used": pattern_name,
                        "raw_parts": len(parts),
                    },
                )

        # Fallback: simple text splitting
        parts = split_text(full_text, max_tokens=max_tokens)
        chunks = self._parts_to_chunks_with_metadata(
            parts, max_tokens, full_text, elements, element_offsets
        )

        return ChunkResult(
            chunks=chunks,
            strategy_used=self.name,
            stats={"pattern_used": "fallback", "raw_parts": len(parts)},
        )

    def _find_element_for_text(
        self,
        part: str,
        full_text: str,
        elements: list,
        element_offsets: list[tuple[int, int]],
    ) -> tuple[int | None, str]:
        """Find the page and section for a text part by locating it in full_text."""
        idx = full_text.find(part[:100])  # Match by first 100 chars
        if idx < 0:
            return None, ""
        for i, (start, end) in enumerate(element_offsets):
            if start <= idx < end:
                return elements[i].page, elements[i].section
        return None, ""

    def _parts_to_chunks_with_metadata(
        self,
        parts: list[str],
        max_tokens: int,
        full_text: str,
        elements: list,
        element_offsets: list[tuple[int, int]],
    ) -> list[RawChunk]:
        """Convert split parts to chunks with page/section from source elements."""
        chunks: list[RawChunk] = []
        for part in parts:
            page, section = self._find_element_for_text(
                part, full_text, elements, element_offsets
            )
            tokens = estimate_tokens(part)
            if tokens <= max_tokens:
                chunks.append(RawChunk(
                    text=part,
                    chunk_type="text",
                    section=section,
                    page=page,
                    token_count=tokens,
                ))
            else:
                sub_parts = split_text(part, max_tokens=max_tokens)
                for sp in sub_parts:
                    chunks.append(RawChunk(
                        text=sp,
                        chunk_type="text",
                        section=section,
                        page=page,
                        token_count=estimate_tokens(sp),
                    ))
        return chunks
