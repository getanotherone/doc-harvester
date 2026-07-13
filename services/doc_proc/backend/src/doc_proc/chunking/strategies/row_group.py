"""Row-group chunking — groups N rows per chunk.

Groups `group_size` data rows per chunk, respecting section boundaries.
Good balance between granularity and context.
"""

from __future__ import annotations

from doc_proc.models import ChunkResult, ParseResult, RawChunk, estimate_tokens


class RowGroupChunker:
    """Group N consecutive rows into one chunk."""

    name = "row_group"

    def chunk(
        self,
        parse_result: ParseResult,
        *,
        group_size: int = 30,
        **kwargs,
    ) -> ChunkResult:
        chunks: list[RawChunk] = []
        buffer: list[str] = []
        current_section = ""
        first_page: int | None = None
        has_table_rows = False

        for el in parse_result.elements:
            if el.element_type in ("section_header", "heading"):
                # Flush on section boundary
                if buffer:
                    ctype = "table" if has_table_rows else "text"
                    chunks.append(self._make_chunk(buffer, current_section, first_page, ctype))
                    buffer = []
                    first_page = None
                    has_table_rows = False
                current_section = el.text
                continue

            if not el.text.strip():
                continue

            if first_page is None:
                first_page = el.page
            if el.row_type == "table_row":
                has_table_rows = True

            buffer.append(el.text)

            if len(buffer) >= group_size:
                ctype = "table" if has_table_rows else "text"
                chunks.append(self._make_chunk(buffer, current_section, first_page, ctype))
                buffer = []
                first_page = None
                has_table_rows = False

        # Final flush
        if buffer:
            ctype = "table" if has_table_rows else "text"
            chunks.append(self._make_chunk(buffer, current_section, first_page, ctype))

        return ChunkResult(
            chunks=chunks,
            strategy_used=self.name,
            stats={"total_elements": len(parse_result.elements), "group_size": group_size},
        )

    def _make_chunk(
        self, lines: list[str], section: str, page: int | None, chunk_type: str = "text"
    ) -> RawChunk:
        text = "\n".join(lines)
        return RawChunk(
            text=text,
            chunk_type=chunk_type,
            section=section,
            page=page,
            token_count=estimate_tokens(text),
        )
