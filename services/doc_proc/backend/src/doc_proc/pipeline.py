"""Pipeline orchestrator — coordinates Parse → Filter → Chunk → Embed → Evaluate."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

from doc_proc.models import (
    ChunkResult,
    ComparisonResult,
    EmbeddedChunk,
    EmbedResult,
    ParseResult,
    QualityReport,
    estimate_tokens,
)

logger = logging.getLogger(__name__)


@dataclass
class PipelineConfig:
    """Unified pipeline configuration."""

    # Parsing
    force_docling: bool = False
    ocr_engine: str = "tesseract"
    ocr_languages: str = "rus+eng"
    max_pdf_ocr_size_mb: int = 50

    # Filtering
    min_text_length: int = 20
    skip_metadata: bool = True
    skip_ocr_garbage: bool = True
    skip_cid_garbage: bool = True
    exclude_patterns: list[str] = field(default_factory=list)
    include_patterns: list[str] = field(default_factory=list)
    content_filter: bool = False  # PDF noise filter

    # Domain metadata extraction
    extract_domain_metadata: bool = True

    # Chunking
    strategy: str = "auto"  # auto, hierarchical, structure_aware, row_level, etc.
    max_tokens: int = 1000
    overlap_tokens: int = 50
    group_size: int = 30

    # Context
    inject_context: bool = True
    doc_title: str = ""
    domain_context: str = ""

    # Embedding
    embed: bool = True
    embedding_batch_size: int = 64


class Pipeline:
    """Orchestrates the full document processing pipeline."""

    def __init__(self, config: PipelineConfig | None = None):
        self.config = config or PipelineConfig()

    def parse(self, content: bytes, filename: str) -> ParseResult:
        """Stage 1: Parse document into typed elements."""
        from doc_proc.parsing.router import parse_document

        return parse_document(
            content,
            filename,
            force_docling=self.config.force_docling,
            ocr_engine=self.config.ocr_engine,
            ocr_languages=self.config.ocr_languages,
            max_pdf_ocr_size_mb=self.config.max_pdf_ocr_size_mb,
        )

    def filter(self, parse_result: ParseResult) -> ParseResult:
        """Stage 2: Filter parsed elements (content noise, metadata)."""
        if self.config.content_filter:
            from doc_proc.parsing.filters.content import filter_elements

            parse_result.elements = filter_elements(parse_result.elements)

        return parse_result

    def chunk(self, parse_result: ParseResult) -> ChunkResult:
        """Stage 3: Chunk elements using selected strategy."""
        from doc_proc.chunking.registry import auto_select, get_chunker

        strategy = self.config.strategy
        if strategy == "auto":
            strategy = auto_select(parse_result)

        chunker = get_chunker(strategy)
        chunk_result = chunker.chunk(
            parse_result,
            max_tokens=self.config.max_tokens,
            overlap_tokens=self.config.overlap_tokens,
            group_size=self.config.group_size,
        )

        # Apply filters
        from doc_proc.chunking.filters import apply_filters

        chunk_result.chunks = apply_filters(
            chunk_result.chunks,
            min_text_length=self.config.min_text_length,
            skip_metadata=self.config.skip_metadata,
            skip_ocr_garbage=self.config.skip_ocr_garbage,
            skip_cid_garbage=self.config.skip_cid_garbage,
            exclude_patterns=self.config.exclude_patterns,
            include_patterns=self.config.include_patterns,
        )

        # Inject context headers
        if self.config.inject_context:
            from doc_proc.chunking.context import inject_context_headers

            chunk_result.chunks = inject_context_headers(
                chunk_result.chunks,
                doc_title=self.config.doc_title,
                domain_context=self.config.domain_context,
            )

        chunk_result.strategy_used = strategy
        return chunk_result

    def enrich_metadata(self, chunk_result: ChunkResult, filename: str) -> ChunkResult:
        """Enrich chunks with domain-specific metadata (vendor, standard, doc_type, lang)."""
        from doc_proc.domain.metadata import infer_metadata

        for chunk in chunk_result.chunks:
            meta = infer_metadata(
                chunk.text,
                document_name=filename,
                section=chunk.section,
            )
            chunk.vendor = meta["vendor"]
            chunk.standard_id = meta["standard_id"]
            chunk.doc_type = meta["doc_type"]
            chunk.lang = meta["lang"]
            chunk.source_type = meta["source_type"]
            chunk.year = meta["year"]
        return chunk_result

    async def embed(self, chunk_result: ChunkResult) -> EmbedResult:
        """Stage 4: Embed chunks with vector embeddings."""
        from doc_proc.embedding.factory import create_embedding_provider

        embedder = create_embedding_provider()
        texts = [c.text for c in chunk_result.chunks]

        embeddings = await embedder.embed_batch(texts)

        embedded = [
            EmbeddedChunk(chunk=chunk, embedding=emb)
            for chunk, emb in zip(chunk_result.chunks, embeddings)
        ]

        return EmbedResult(
            chunks=embedded,
            model=getattr(embedder, "model", "unknown"),
            dimension=embedder.dimension(),
        )

    def evaluate(self, chunk_result: ChunkResult) -> QualityReport:
        """Stage 5: Evaluate chunk quality."""
        chunks = chunk_result.chunks
        if not chunks:
            return QualityReport()

        token_counts = [c.token_count or estimate_tokens(c.text) for c in chunks]
        by_type: dict[str, int] = {}
        by_section: dict[str, int] = {}

        for c in chunks:
            by_type[c.chunk_type] = by_type.get(c.chunk_type, 0) + 1
            if c.section:
                by_section[c.section] = by_section.get(c.section, 0) + 1

        return QualityReport(
            total_chunks=len(chunks),
            total_tokens=sum(token_counts),
            avg_tokens=sum(token_counts) / len(token_counts),
            min_tokens=min(token_counts),
            max_tokens=max(token_counts),
            by_type=by_type,
            by_section=by_section,
        )

    async def run(
        self, content: bytes, filename: str
    ) -> tuple[ChunkResult, EmbedResult | None, QualityReport]:
        """Run the full pipeline: parse → filter → chunk → embed → evaluate."""
        parse_result = self.parse(content, filename)
        parse_result = self.filter(parse_result)
        chunk_result = self.chunk(parse_result)

        if self.config.extract_domain_metadata:
            chunk_result = self.enrich_metadata(chunk_result, filename)

        embed_result = None
        if self.config.embed:
            embed_result = await self.embed(chunk_result)

        quality = self.evaluate(chunk_result)

        logger.info(
            "Pipeline complete: %s → %d chunks, %d tokens, strategy=%s",
            filename, quality.total_chunks, quality.total_tokens,
            chunk_result.strategy_used,
        )

        return chunk_result, embed_result, quality

    async def compare(
        self,
        content: bytes,
        filename: str,
        strategies: list[str],
        *,
        embed: bool = False,
    ) -> ComparisonResult:
        """Run multiple strategies on the same document and compare results."""
        parse_result = self.parse(content, filename)
        parse_result = self.filter(parse_result)

        result = ComparisonResult(document_id=filename)

        for strategy in strategies:
            from doc_proc.chunking.registry import get_chunker

            chunker = get_chunker(strategy)
            chunk_result = chunker.chunk(
                parse_result,
                max_tokens=self.config.max_tokens,
                overlap_tokens=self.config.overlap_tokens,
                group_size=self.config.group_size,
            )

            from doc_proc.chunking.filters import apply_filters

            chunk_result.chunks = apply_filters(
                chunk_result.chunks,
                min_text_length=self.config.min_text_length,
                skip_metadata=self.config.skip_metadata,
            )

            quality = self.evaluate(chunk_result)
            result.strategies[strategy] = quality

            # Sample chunks (first 5)
            result.sample_chunks[strategy] = [
                {"text": c.text[:200], "type": c.chunk_type, "section": c.section}
                for c in chunk_result.chunks[:5]
            ]

        return result
