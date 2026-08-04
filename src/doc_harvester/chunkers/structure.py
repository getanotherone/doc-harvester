"""Structure-aware adapter over the standalone chunking implementation."""

from __future__ import annotations

from chunker import build_blocks_from_units, chunk_blocks_v2

from doc_harvester.core import Chunk, Chunker, ChunkingOptions, ExtractedDocument


class StructureAwareChunker(Chunker):
    """Preserve tables/normative blocks while enforcing an explicit token ceiling."""

    name = "structure-aware"

    def chunk(
        self,
        document: ExtractedDocument,
        options: ChunkingOptions,
    ) -> list[Chunk]:
        if options.strategy not in {"default", self.name}:
            raise ValueError(f"unsupported strategy for {self.name}: {options.strategy}")

        units = [
            {
                "document": document.resource.uri,
                "page": block.page or index + 1,
                "section": block.section,
                "text": block.text,
            }
            for index, block in enumerate(document.blocks)
            if block.text.strip()
        ]
        blocks = build_blocks_from_units(units)
        target_tokens = max(1, int(options.max_tokens * 0.8))
        result = chunk_blocks_v2(
            blocks,
            target_tokens=target_tokens,
            max_tokens=options.max_tokens,
        )

        chunks: list[Chunk] = []
        for index, payload in enumerate(result["chunks"]):
            metadata = {
                key: value
                for key, value in payload.items()
                if key not in {"chunk_index", "text"}
            }
            metadata["oversized"] = int(metadata.get("token_count", 0)) > options.max_tokens
            chunks.append(Chunk(payload["text"], index, metadata))
        return chunks

