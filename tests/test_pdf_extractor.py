from __future__ import annotations

import pytest

from doc_harvester.core import FetchedArtifact, ResourceRef
from doc_harvester.extractors import PDFExtractor, select_extractor
from tests.pdf_fixture import build_text_pdf


def artifact(content: bytes, *, filename: str = "guide.pdf") -> FetchedArtifact:
    resource = ResourceRef(filename, source="test", media_type="application/pdf")
    return FetchedArtifact(
        resource,
        content,
        media_type="application/pdf",
        filename=filename,
    )


def test_pdf_extractor_preserves_page_numbers_and_metadata():
    source = artifact(build_text_pdf("First page technical content.", "Second page."))

    document = PDFExtractor().extract(source)

    assert [block.text for block in document.blocks] == [
        "First page technical content.",
        "Second page.",
    ]
    assert [block.page for block in document.blocks] == [1, 2]
    assert document.metadata == {
        "extractor": "pdf",
        "filename": "guide.pdf",
        "media_type": "application/pdf",
        "page_count": 2,
        "pages_with_text": 2,
        "empty_pages": [],
        "ocr_used": False,
        "ocr_required": False,
    }


def test_pdf_extractor_reports_image_only_candidate_without_running_ocr():
    document = PDFExtractor().extract(artifact(build_text_pdf("")))

    assert document.blocks == ()
    assert document.metadata["empty_pages"] == [1]
    assert document.metadata["ocr_used"] is False
    assert document.metadata["ocr_required"] is True


def test_pdf_extractor_enforces_page_limit():
    with pytest.raises(ValueError, match="configured page limit"):
        PDFExtractor(max_pages=1).extract(artifact(build_text_pdf("One", "Two")))


@pytest.mark.parametrize("content", [b"not a PDF", b"%PDF-broken"])
def test_pdf_extractor_rejects_invalid_content_with_safe_error(content):
    with pytest.raises(ValueError, match="invalid PDF signature|PDF extraction failed"):
        PDFExtractor().extract(artifact(content))


def test_pdf_factory_selection_accepts_media_type_or_extension():
    selected = select_extractor(artifact(build_text_pdf("Text")), max_pdf_pages=10)

    assert isinstance(selected, PDFExtractor)
    assert selected.max_pages == 10
