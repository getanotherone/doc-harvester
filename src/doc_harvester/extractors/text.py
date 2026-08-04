"""Plain-text and Markdown extractor adapter."""

from __future__ import annotations

from urllib.parse import urlsplit

from chunker import normalize_text, split_into_paragraphs

from doc_harvester.core import ContentBlock, ExtractedDocument, Extractor, FetchedArtifact


class TextExtractor(Extractor):
    """Extract normalized paragraphs from UTF-8-compatible text resources."""

    name = "text"
    _MEDIA_TYPES = {"text/plain", "text/markdown"}
    _EXTENSIONS = {".txt", ".md", ".markdown"}

    def supports(self, artifact: FetchedArtifact) -> bool:
        media_type = artifact.media_type.split(";", 1)[0].strip().lower()
        suffix = self._suffix(artifact)
        return media_type in self._MEDIA_TYPES or suffix in self._EXTENSIONS

    def extract(self, artifact: FetchedArtifact) -> ExtractedDocument:
        if not self.supports(artifact):
            raise ValueError(f"{self.name} extractor does not support this artifact")
        decoded = artifact.content.decode("utf-8-sig", errors="replace")
        normalized = normalize_text(decoded)
        paragraphs = split_into_paragraphs(normalized)
        blocks = tuple(ContentBlock(text, kind="text") for text in paragraphs)
        return ExtractedDocument(
            artifact.resource,
            blocks,
            metadata={
                "extractor": self.name,
                "filename": artifact.filename,
                "media_type": artifact.media_type,
            },
        )

    @staticmethod
    def _suffix(artifact: FetchedArtifact) -> str:
        candidate = artifact.filename or urlsplit(artifact.resource.uri).path
        lowered = candidate.lower()
        return next(
            (extension for extension in TextExtractor._EXTENSIONS if lowered.endswith(extension)),
            "",
        )

