"""Hierarchical chunking — section-aware grouping for tabular data.

Default strategy for Excel/CSV. Groups rows by section boundaries,
builds markdown tables from table rows, splits text runs.
"""

from __future__ import annotations

import re

from doc_proc.models import (
    CHARS_PER_TOKEN,
    ChunkResult,
    ParseResult,
    RawChunk,
    estimate_tokens,
)

_NUMBERED_RE = re.compile(r"^\d{1,3}[\.\)]\s+")
_ALL_CAPS_RE = re.compile(r"^[A-ZА-ЯЁ\s\d\-\.\,]{8,}$")


class HierarchicalChunker:
    """Section-aware hierarchical chunker for tabular data."""

    name = "hierarchical"

    def chunk(
        self,
        parse_result: ParseResult,
        *,
        max_tokens: int = 512,
        overlap_tokens: int = 50,
        group_by_section: bool = True,
        group_size: int = 30,
        **kwargs,
    ) -> ChunkResult:
        elements = parse_result.elements
        if not elements:
            return ChunkResult(chunks=[], strategy_used=self.name)

        chunks: list[RawChunk] = []
        heading_stack: list[tuple[int, str]] = []
        current_section = ""
        buffer: list[dict] = []
        buffer_type = "text"
        last_text_context = ""

        for el in elements:
            if el.element_type in ("section_header", "heading"):
                # Flush buffer on section change
                if buffer:
                    chunks.extend(self._flush_buffer(
                        buffer, buffer_type, current_section,
                        max_tokens, last_text_context,
                    ))
                    buffer = []

                level = self._infer_heading_level(el.text)
                heading_stack = [
                    (heading_level, title)
                    for heading_level, title in heading_stack
                    if heading_level < level
                ]
                heading_stack.append((level, el.text))
                current_section = " / ".join(t for _, t in heading_stack)
                continue

            # Determine element type
            el_type = "table" if el.row_type == "table_row" else "text"

            # Flush on type change
            if buffer and el_type != buffer_type:
                chunks.extend(self._flush_buffer(
                    buffer, buffer_type, current_section,
                    max_tokens, last_text_context,
                ))
                buffer = []

            buffer_type = el_type
            buffer.append({"text": el.text, "page": el.page, "attrs": el.attributes})

            if el_type == "text" and len(el.text) > 20:
                last_text_context = el.text

            # Flush on group size
            if group_by_section and len(buffer) >= group_size:
                chunks.extend(self._flush_buffer(
                    buffer, buffer_type, current_section,
                    max_tokens, last_text_context,
                ))
                buffer = []

        # Final flush
        if buffer:
            chunks.extend(self._flush_buffer(
                buffer, buffer_type, current_section,
                max_tokens, last_text_context,
            ))

        for i, c in enumerate(chunks):
            c.token_count = estimate_tokens(c.text)

        return ChunkResult(
            chunks=chunks,
            strategy_used=self.name,
            stats={"total_elements": len(elements)},
        )

    def _flush_buffer(
        self,
        buffer: list[dict],
        buffer_type: str,
        section: str,
        max_tokens: int,
        last_text_context: str,
    ) -> list[RawChunk]:
        if buffer_type == "table":
            return self._build_table_chunks(buffer, section, max_tokens, last_text_context)
        return self._build_text_chunks(buffer, section, max_tokens)

    def _build_table_chunks(
        self,
        rows: list[dict],
        section: str,
        max_tokens: int,
        context: str,
    ) -> list[RawChunk]:
        """Build markdown table chunks from row buffer."""
        chunks: list[RawChunk] = []
        max_chars = max_tokens * CHARS_PER_TOKEN
        current_text = ""
        chunk_start_page = rows[0].get("page") if rows else None

        for row in rows:
            line = row["text"] + "\n"
            if len(current_text) + len(line) > max_chars and current_text:
                chunks.append(RawChunk(
                    text=current_text.rstrip(),
                    chunk_type="table",
                    section=section,
                    page=chunk_start_page,
                    context_header=context,
                ))
                current_text = ""
                chunk_start_page = row.get("page")
            current_text += line

        if current_text.strip():
            chunks.append(RawChunk(
                text=current_text.rstrip(),
                chunk_type="table",
                section=section,
                page=chunk_start_page,
                context_header=context,
            ))
        return chunks

    def _build_text_chunks(
        self,
        rows: list[dict],
        section: str,
        max_tokens: int,
    ) -> list[RawChunk]:
        """Build text chunks from text element buffer."""
        from doc_proc.chunking.splitters import split_text

        full_text = "\n".join(r["text"] for r in rows)
        if not full_text.strip():
            return []

        parts = split_text(full_text, max_tokens=max_tokens)
        return [
            RawChunk(
                text=part,
                chunk_type="text",
                section=section,
                page=rows[0].get("page"),
            )
            for part in parts
        ]

    def _infer_heading_level(self, text: str) -> int:
        """Infer heading level from text characteristics."""
        if _ALL_CAPS_RE.match(text):
            return 1
        if _NUMBERED_RE.match(text):
            return 2
        return 3
