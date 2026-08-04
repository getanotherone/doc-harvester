from __future__ import annotations

import pytest

from doc_harvester.chunkers import StructureAwareChunker
from doc_harvester.core import ChunkingOptions, FetchedArtifact, ResourceRef
from doc_harvester.extractors import DOCXExtractor, select_extractor
from tests.docx_fixture import WORD_NS, build_docx, paragraph, table


MEDIA_TYPE = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"


def artifact(content: bytes, *, filename: str = "guide.docx") -> FetchedArtifact:
    resource = ResourceRef(filename, source="test", media_type=MEDIA_TYPE)
    return FetchedArtifact(resource, content, media_type=MEDIA_TYPE, filename=filename)


def test_docx_extractor_preserves_headings_lists_tables_and_sections():
    source = artifact(
        build_docx(
            paragraph("Installation", style="Heading1")
            + paragraph("Follow the technical requirements.")
            + paragraph("Disconnect power first.", numbered=True)
            + table(("Model", "Rating"), ("A-1", "16 | 20 A"))
        )
    )

    document = DOCXExtractor().extract(source)

    assert [(block.kind, block.text, block.section) for block in document.blocks] == [
        ("heading", "Installation", "Installation"),
        ("text", "Follow the technical requirements.", "Installation"),
        ("list_item", "Disconnect power first.", "Installation"),
        ("table", "Model | Rating", "Installation"),
        ("table", "A-1 | 16 \\| 20 A", "Installation"),
    ]
    assert document.blocks[-1].metadata == {
        "table_index": 0,
        "row_index": 1,
        "columns": 2,
    }
    assert document.metadata == {
        "extractor": "docx",
        "filename": "guide.docx",
        "media_type": MEDIA_TYPE,
        "block_count": 5,
        "paragraph_count": 1,
        "heading_count": 1,
        "list_item_count": 1,
        "table_count": 1,
        "table_row_count": 2,
    }

    chunks = StructureAwareChunker().chunk(
        document,
        ChunkingOptions(strategy="structure-aware", max_tokens=100, overlap_tokens=0),
    )
    assert chunks[0].metadata["section"] == "Installation"
    assert chunks[0].metadata["page"] is None
    assert chunks[0].metadata["start_page"] is None
    assert chunks[0].metadata["end_page"] is None
    assert "table" in chunks[0].metadata["block_types"]


def test_docx_factory_selection_forwards_safety_bounds():
    selected = select_extractor(
        artifact(build_docx(paragraph("Text"))),
        max_docx_blocks=7,
        max_docx_uncompressed_bytes=12_345,
    )

    assert isinstance(selected, DOCXExtractor)
    assert selected.max_blocks == 7
    assert selected.max_uncompressed_bytes == 12_345


def test_docx_extractor_supports_strict_ooxml_namespace():
    strict_namespace = "http://purl.oclc.org/ooxml/wordprocessingml/main"
    source = artifact(
        build_docx(
            paragraph("Strict OOXML content."),
            word_namespace=strict_namespace,
        )
    )

    document = DOCXExtractor().extract(source)

    assert WORD_NS != strict_namespace
    assert [block.text for block in document.blocks] == ["Strict OOXML content."]


@pytest.mark.parametrize(
    ("content", "message"),
    [
        (b"not a DOCX", "signature"),
        (b"PK broken", "extraction failed"),
        (build_docx("", include_document=False), "missing required"),
        (
            build_docx("<!DOCTYPE x><w:p><w:r><w:t>Unsafe</w:t></w:r></w:p>"),
            "declarations are not allowed",
        ),
    ],
)
def test_docx_extractor_rejects_invalid_containers_safely(content, message):
    with pytest.raises(ValueError, match=message):
        DOCXExtractor().extract(artifact(content))


def test_docx_extractor_enforces_block_entry_and_expanded_byte_limits():
    two_blocks = artifact(build_docx(paragraph("One") + paragraph("Two")))
    with pytest.raises(ValueError, match="block limit"):
        DOCXExtractor(max_blocks=1).extract(two_blocks)

    extra_entry = artifact(
        build_docx(paragraph("One"), extra_entries={"word/extra.xml": b"x"})
    )
    with pytest.raises(ValueError, match="entry limit"):
        DOCXExtractor(max_entries=2).extract(extra_entry)

    with pytest.raises(ValueError, match="uncompressed-byte limit"):
        DOCXExtractor(max_uncompressed_bytes=10).extract(two_blocks)


def test_docx_extractor_rejects_oversized_main_xml_before_parsing():
    source = artifact(build_docx(paragraph("A sufficiently long paragraph.")))

    with pytest.raises(ValueError, match="XML-byte limit"):
        DOCXExtractor(max_document_xml_bytes=20).extract(source)
