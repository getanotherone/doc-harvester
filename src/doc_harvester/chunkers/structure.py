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

        blocks = []
        uses_flow_layout = document.metadata.get("extractor") in {"docx", "xlsx"}
        for index, content_block in enumerate(document.blocks):
            if not content_block.text.strip():
                continue
            page = content_block.page
            if page is None:
                page = 0 if uses_flow_layout else index + 1
            converted = build_blocks_from_units(
                [
                    {
                        "document": document.resource.uri,
                        "page": page,
                        "unit_index": page,
                        "text": content_block.text,
                    }
                ]
            )
            for block in converted:
                section = content_block.section
                if content_block.kind == "heading":
                    section = content_block.text
                if section:
                    block["section"] = section
                    block["section_path"] = [section]
                    block["section_level"] = 1
                if content_block.kind != "text":
                    block["block_types"] = sorted(
                        set(block["block_types"]) | {content_block.kind}
                    )
                blocks.append(block)
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
            for key in ("page", "start_page", "end_page"):
                if metadata.get(key) == 0:
                    metadata[key] = None
            chunks.append(Chunk(payload["text"], index, metadata))
        return chunks
