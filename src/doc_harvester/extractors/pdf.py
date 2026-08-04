"""Digital-text PDF extractor adapter."""

from __future__ import annotations

from io import BytesIO
from urllib.parse import urlsplit

from pdfminer.high_level import extract_pages
from pdfminer.layout import LTTextContainer

from chunker import normalize_text, split_into_paragraphs
from doc_harvester.core import ContentBlock, ExtractedDocument, Extractor, FetchedArtifact


class _PDFPageLimitExceeded(Exception):
    pass


class PDFExtractor(Extractor):
    """Extract page-aware text from PDFs without invoking external OCR tools."""

    name = "pdf"
    _MEDIA_TYPES = {"application/pdf", "application/x-pdf"}

    def __init__(self, *, max_pages: int = 1000) -> None:
        if max_pages < 1:
            raise ValueError("PDF max pages must be at least 1")
        self.max_pages = max_pages

    def supports(self, artifact: FetchedArtifact) -> bool:
        media_type = artifact.media_type.split(";", 1)[0].strip().lower()
        candidate = artifact.filename or urlsplit(artifact.resource.uri).path
        return media_type in self._MEDIA_TYPES or candidate.lower().endswith(".pdf")

    def extract(self, artifact: FetchedArtifact) -> ExtractedDocument:
        if not self.supports(artifact):
            raise ValueError(f"{self.name} extractor does not support this artifact")
        if not artifact.content.lstrip().startswith(b"%PDF-"):
            raise ValueError("invalid PDF signature")

        blocks: list[ContentBlock] = []
        page_count = 0
        empty_pages: list[int] = []
        try:
            for page_count, layout in enumerate(
                extract_pages(BytesIO(artifact.content)), start=1
            ):
                if page_count > self.max_pages:
                    raise _PDFPageLimitExceeded
                raw_text = "\n".join(
                    element.get_text()
                    for element in layout
                    if isinstance(element, LTTextContainer)
                )
                paragraphs = split_into_paragraphs(normalize_text(raw_text))
                if not paragraphs:
                    empty_pages.append(page_count)
                    continue
                blocks.extend(
                    ContentBlock(text, kind="text", page=page_count)
                    for text in paragraphs
                )
        except _PDFPageLimitExceeded:
            raise ValueError(
                f"PDF exceeds configured page limit ({self.max_pages})"
            ) from None
        except Exception as error:
            raise ValueError(f"PDF extraction failed: {type(error).__name__}") from None

        return ExtractedDocument(
            artifact.resource,
            tuple(blocks),
            metadata={
                "extractor": self.name,
                "filename": artifact.filename,
                "media_type": artifact.media_type,
                "page_count": page_count,
                "pages_with_text": page_count - len(empty_pages),
                "empty_pages": empty_pages,
                "ocr_used": False,
                "ocr_required": bool(page_count and not blocks),
            },
        )
