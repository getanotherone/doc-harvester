"""Row-level chunking — each data row becomes one chunk.

Best for structured data where each row is an independent material/equipment record.
Preserves individual records for direct normalization matching.
"""

from __future__ import annotations

from doc_proc.models import ChunkResult, ParseResult, RawChunk, estimate_tokens


class RowLevelChunker:
    """One row = one chunk. Best for structured tabular data."""

    name = "row_level"

    def chunk(self, parse_result: ParseResult, **kwargs) -> ChunkResult:
        chunks: list[RawChunk] = []
        current_section = ""

        for el in parse_result.elements:
            if el.element_type in ("section_header", "heading"):
                current_section = el.text
                continue

            if not el.text.strip():
                continue

            chunks.append(RawChunk(
                text=el.text,
                chunk_type="table" if el.row_type == "table_row" else "text",
                section=el.section or current_section,
                page=el.page,
                metadata=el.attributes if el.attributes else {},
                token_count=estimate_tokens(el.text),
            ))

        return ChunkResult(
            chunks=chunks,
            strategy_used=self.name,
            stats={"total_elements": len(parse_result.elements)},
        )
