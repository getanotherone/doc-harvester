from __future__ import annotations

import pytest

from doc_harvester.chunkers import (
    StructureAwareChunker,
    available_chunkers,
    create_chunker,
)
from doc_harvester.core import ChunkingOptions, FetchedArtifact, ResourceRef
from doc_harvester.extractors import (
    HTMLExtractor,
    PDFExtractor,
    TextExtractor,
    available_extractors,
    create_extractor,
    select_extractor,
)


def artifact(content, *, filename, media_type):
    return FetchedArtifact(
        ResourceRef(f"memory:///{filename}", media_type=media_type),
        content,
        media_type=media_type,
        filename=filename,
    )


def test_text_extractor_normalizes_markdown_paragraphs():
    source = artifact(
        b"# Heading\r\n\r\nFirst   paragraph.\n\nSecond paragraph.",
        filename="guide.md",
        media_type="text/markdown",
    )
    extractor = TextExtractor()

    document = extractor.extract(source)

    assert extractor.supports(source)
    assert [block.text for block in document.blocks] == [
        "# Heading",
        "First paragraph.",
        "Second paragraph.",
    ]
    assert document.metadata["extractor"] == "text"


def test_html_extractor_removes_navigation_and_preserves_content():
    source = artifact(
        b"<html><body><nav>Menu</nav><main><h1>Guide</h1>"
        b"<p>Technical content.</p><p>Second useful paragraph.</p></main></body></html>",
        filename="guide.html",
        media_type="text/html",
    )

    document = HTMLExtractor().extract(source)

    extracted = "\n".join(block.text for block in document.blocks)
    assert "Guide" in extracted
    assert "Technical content" in extracted
    assert "Menu" not in extracted


def test_html_extractor_is_not_tied_to_legacy_commercial_filters():
    source = artifact(
        "<main><p>Нужна помощь в выборе оборудования.</p>"
        "<p>Delivery and pricing are part of this source.</p></main>".encode(),
        filename="guide.html",
        media_type="text/html",
    )

    extracted = "\n".join(block.text for block in HTMLExtractor().extract(source).blocks)

    assert "Нужна помощь" in extracted
    assert "Delivery and pricing" in extracted


def test_xml_extractor_falls_back_to_custom_element_text():
    source = artifact(
        b"<?xml version='1.0'?><catalog><technical-note>Useful XML content"
        b"</technical-note></catalog>",
        filename="catalog.xml",
        media_type="application/xml",
    )

    document = HTMLExtractor().extract(source)

    assert [block.text for block in document.blocks] == ["Useful XML content"]


def test_extractor_selection_accepts_pdf_but_text_extractor_rejects_it():
    source = artifact(b"%PDF", filename="guide.pdf", media_type="application/pdf")

    assert isinstance(select_extractor(source), PDFExtractor)
    with pytest.raises(ValueError, match="does not support"):
        TextExtractor().extract(source)


def test_structure_aware_chunker_returns_indexed_bounded_chunks():
    text = "\n\n".join(
        f"Section {index}. This sentence describes a technical requirement in detail."
        for index in range(30)
    )
    document = TextExtractor().extract(
        artifact(text.encode(), filename="guide.txt", media_type="text/plain")
    )
    chunker = StructureAwareChunker()

    chunks = chunker.chunk(
        document,
        ChunkingOptions(strategy="structure-aware", max_tokens=80, overlap_tokens=0),
    )

    assert [chunk.index for chunk in chunks] == list(range(len(chunks)))
    assert len(chunks) > 1
    assert all(chunk.text for chunk in chunks)
    assert all(
        chunk.metadata["token_count"] <= 80 or chunk.metadata["oversized"]
        for chunk in chunks
    )


def test_processing_adapter_factories_list_and_build_supported_adapters():
    assert available_extractors() == ("text", "html-xml", "pdf")
    assert isinstance(create_extractor("xml"), HTMLExtractor)
    assert isinstance(create_extractor("pdf"), PDFExtractor)
    assert available_chunkers() == ("structure-aware",)
    assert isinstance(create_chunker("default"), StructureAwareChunker)
    with pytest.raises(ValueError, match="unknown extractor"):
        create_extractor("docx")
    with pytest.raises(ValueError, match="unknown chunker"):
        create_chunker("semantic")
