"""Structure-aware chunking — semantic grouping for PDF/DOCX.

Default strategy for Docling-parsed documents. Groups elements by heading
transitions into semantic blocks, then splits blocks that exceed token limits.
"""

from __future__ import annotations

from doc_proc.domain.block_classifier import is_normative_block
from doc_proc.models import (
    ChunkResult,
    ParseResult,
    RawChunk,
    estimate_tokens,
)

# Token limits per chunk type (tuned for electrical engineering specs)
TOKEN_LIMITS = {
    "text": 1000,
    "list": 1000,
    "table": 1000,
    "mixed": 1000,
    "heading": 128,
    "image": 512,
    "normative": 1200,  # Protected: numbered requirements
}

# Max elements in a single block before forcing a page-based split
MAX_BLOCK_ELEMENTS = 200


class StructureAwareChunker:
    """Semantic grouping chunker for document-format files (PDF/DOCX)."""

    name = "structure_aware"

    def chunk(
        self,
        parse_result: ParseResult,
        *,
        max_tokens: int = 1000,
        overlap_tokens: int = 50,
        **kwargs,
    ) -> ChunkResult:
        elements = parse_result.elements
        if not elements:
            return ChunkResult(chunks=[], strategy_used=self.name)

        # Phase 1: Group elements into semantic blocks by heading transitions
        blocks = self._group_into_blocks(elements)

        # Phase 2: Chunk each block, splitting if oversized
        chunks: list[RawChunk] = []
        for block_section, block_elements in blocks:
            block_text = "\n\n".join(el.text for el in block_elements)
            block_tokens = estimate_tokens(block_text)

            # Determine block type
            types = {el.element_type for el in block_elements}
            row_types = {el.row_type for el in block_elements}
            if "table_row" in row_types:
                block_type = "table"
                limit = TOKEN_LIMITS["table"]
            elif is_normative_block(block_text):
                block_type = "normative"
                limit = TOKEN_LIMITS["normative"]
            elif len(types) > 1:
                block_type = "mixed"
                limit = TOKEN_LIMITS["mixed"]
            else:
                block_type = "text"
                limit = max_tokens

            # Normative blocks are protected — keep intact even if oversized
            protected = block_type in ("normative", "table")

            if block_tokens <= limit or (protected and block_tokens <= limit * 1.2):
                chunks.append(RawChunk(
                    text=block_text,
                    chunk_type=block_type,
                    section=block_section,
                    page=block_elements[0].page if block_elements else None,
                    token_count=block_tokens,
                    metadata={"block_types": [block_type]},
                ))
            else:
                # Split oversized block
                sub_chunks = self._split_block(
                    block_elements, block_section, block_type, limit,
                    overlap_tokens=overlap_tokens,
                )
                chunks.extend(sub_chunks)

        # Phase 3: Merge tiny adjacent chunks
        chunks = self._merge_small(chunks, min_tokens=150)

        return ChunkResult(
            chunks=chunks,
            strategy_used=self.name,
            stats={"total_elements": len(elements), "blocks": len(blocks)},
        )

    def _group_into_blocks(
        self, elements: list
    ) -> list[tuple[str, list]]:
        """Group elements by heading transitions into semantic blocks.

        Also splits on page boundaries when a block exceeds MAX_BLOCK_ELEMENTS,
        preventing massive single-block documents (e.g. PDFs with no headings).
        """
        blocks: list[tuple[str, list]] = []
        current_section = ""
        current_block: list = []
        last_page = None

        for el in elements:
            if el.element_type in ("heading", "section_header"):
                if current_block:
                    blocks.append((current_section, current_block))
                current_section = el.text
                # Start new block with heading as first element (keeps it searchable)
                current_block = [el]
                last_page = None
                continue

            # Split on page boundary when block is getting too large
            if (
                len(current_block) >= MAX_BLOCK_ELEMENTS
                and el.page is not None
                and last_page is not None
                and el.page != last_page
            ):
                blocks.append((current_section, current_block))
                current_block = []

            current_block.append(el)
            if el.page is not None:
                last_page = el.page

        if current_block:
            blocks.append((current_section, current_block))

        return blocks

    def _split_block(
        self,
        elements: list,
        section: str,
        block_type: str,
        limit: int,
        overlap_tokens: int = 50,
    ) -> list[RawChunk]:
        """Split an oversized block into chunks within token limits."""
        from doc_proc.chunking.splitters import split_text

        chunks: list[RawChunk] = []
        buffer_text = ""
        first_page = elements[0].page if elements else None

        for el in elements:
            el_tokens = estimate_tokens(el.text)

            # Single element exceeds limit → force split
            if el_tokens > limit:
                if buffer_text.strip():
                    chunks.append(RawChunk(
                        text=buffer_text.strip(),
                        chunk_type=block_type,
                        section=section,
                        page=first_page,
                        token_count=estimate_tokens(buffer_text),
                    ))
                    buffer_text = ""

                parts = split_text(el.text, max_tokens=limit, overlap_tokens=overlap_tokens)
                for part in parts:
                    chunks.append(RawChunk(
                        text=part,
                        chunk_type=block_type,
                        section=section,
                        page=el.page,
                        token_count=estimate_tokens(part),
                    ))
                first_page = el.page
                continue

            # Would adding this element exceed limit?
            combined = f"{buffer_text}\n\n{el.text}" if buffer_text else el.text
            if estimate_tokens(combined) > limit and buffer_text:
                chunks.append(RawChunk(
                    text=buffer_text.strip(),
                    chunk_type=block_type,
                    section=section,
                    page=first_page,
                    token_count=estimate_tokens(buffer_text),
                ))
                buffer_text = el.text
                first_page = el.page
            else:
                buffer_text = combined

        if buffer_text.strip():
            chunks.append(RawChunk(
                text=buffer_text.strip(),
                chunk_type=block_type,
                section=section,
                page=first_page,
                token_count=estimate_tokens(buffer_text),
            ))

        return chunks

    def _merge_small(
        self, chunks: list[RawChunk], min_tokens: int = 120
    ) -> list[RawChunk]:
        """Merge adjacent tiny chunks (both directions).

        Same-section merges at min_tokens threshold. Very tiny chunks (<40 tokens)
        are merged even across sections — a 20-token page header is better absorbed
        into the next chunk than left as a standalone fragment.
        """
        if not chunks:
            return chunks

        VERY_TINY = 80  # Cross-section merge threshold

        # Forward pass: merge small prev into next
        merged: list[RawChunk] = [chunks[0]]
        for chunk in chunks[1:]:
            prev = merged[-1]
            same_section = chunk.section == prev.section
            if (
                prev.token_count < min_tokens and same_section
            ) or (
                prev.token_count < VERY_TINY  # merge page headers/footers regardless
            ):
                prev.text = f"{prev.text}\n\n{chunk.text}"
                prev.token_count = estimate_tokens(prev.text)
                if prev.chunk_type == "text" and chunk.chunk_type != "text":
                    prev.chunk_type = chunk.chunk_type
                if not prev.section and chunk.section:
                    prev.section = chunk.section
            else:
                merged.append(chunk)

        # Backward pass: merge trailing small chunk into previous
        if len(merged) >= 2:
            last = merged[-1]
            prev = merged[-2]
            same_section = last.section == prev.section
            if (
                last.token_count < min_tokens and same_section
            ) or (
                last.token_count < VERY_TINY
            ):
                prev.text = f"{prev.text}\n\n{last.text}"
                prev.token_count = estimate_tokens(prev.text)
                merged.pop()

        return merged
