"""Provider- and domain-neutral metadata enrichment."""

from __future__ import annotations

import hashlib
from pathlib import PurePosixPath
from urllib.parse import urlsplit

from doc_harvester.core import (
    Chunk,
    EnrichmentResult,
    ExtractedDocument,
    MetadataEnricher,
)


class BasicMetadataEnricher(MetadataEnricher):
    """Add portable structural, language, size, and content-identity metadata."""

    name = "basic"

    def enrich(
        self,
        document: ExtractedDocument,
        chunks: list[Chunk] | tuple[Chunk, ...],
    ) -> EnrichmentResult:
        source_type = self._source_type(document)
        document_language = self._language(block.text for block in document.blocks)
        document_class = self._document_class(document)
        document_hash = hashlib.sha256()
        document_char_count = 0
        for block in document.blocks:
            document_hash.update(block.text.encode("utf-8"))
            document_hash.update(b"\0")
            document_char_count += len(block.text)

        enriched_document = ExtractedDocument(
            document.resource,
            document.blocks,
            metadata={
                **document.metadata,
                "enricher": self.name,
                "source_type": source_type,
                "language": document_language,
                "document_class": document_class,
                "block_count": len(document.blocks),
                "char_count": document_char_count,
                "content_sha256": document_hash.hexdigest(),
            },
        )

        enriched_chunks = []
        for chunk in chunks:
            normalized = " ".join(chunk.text.split()).lower()
            enriched_chunks.append(
                Chunk(
                    chunk.text,
                    chunk.index,
                    metadata={
                        **chunk.metadata,
                        "enricher": self.name,
                        "source_type": source_type,
                        "language": self._language((chunk.text,)),
                        "document_language": document_language,
                        "document_class": document_class,
                        "char_count": len(chunk.text),
                        "content_sha256": hashlib.sha256(
                            normalized.encode("utf-8")
                        ).hexdigest(),
                    },
                )
            )
        return EnrichmentResult(enriched_document, tuple(enriched_chunks))

    @staticmethod
    def _source_type(document: ExtractedDocument) -> str:
        candidate = str(document.metadata.get("filename", ""))
        if not candidate:
            candidate = urlsplit(document.resource.uri).path
        suffix = PurePosixPath(candidate).suffix.lower().lstrip(".")
        known_suffixes = {
            "txt": "text",
            "htm": "html",
            "html": "html",
            "xhtml": "html",
            "markdown": "markdown",
            "md": "markdown",
            "xml": "xml",
            "pdf": "pdf",
            "docx": "docx",
            "xlsx": "xlsx",
        }
        if suffix in known_suffixes:
            return known_suffixes[suffix]
        media_type = str(document.metadata.get("media_type", "")).split(";", 1)[0]
        from_media_type = {
            "text/plain": "text",
            "text/markdown": "markdown",
            "text/html": "html",
            "application/xhtml+xml": "html",
            "application/xml": "xml",
            "text/xml": "xml",
            "application/pdf": "pdf",
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document": "docx",
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": "xlsx",
        }.get(media_type.lower())
        if from_media_type:
            return from_media_type
        extractor = str(document.metadata.get("extractor", "")).lower()
        return {"html-xml": "html"}.get(extractor, extractor or "unknown")

    @staticmethod
    def _language(texts) -> str:
        cyrillic = latin = 0
        for text in texts:
            for character in text:
                lowered = character.lower()
                cyrillic += "а" <= lowered <= "я" or lowered == "ё"
                latin += "a" <= lowered <= "z"
        if cyrillic and latin:
            return "mixed"
        if cyrillic:
            return "ru"
        if latin:
            return "en"
        return "unknown"

    @staticmethod
    def _document_class(document: ExtractedDocument) -> str:
        kinds = [block.kind for block in document.blocks]
        table_count = kinds.count("table")
        if table_count and table_count * 2 >= len(kinds):
            return "tabular"
        if any(kind in {"heading", "list_item", "table"} for kind in kinds):
            return "structured"
        return "text"
