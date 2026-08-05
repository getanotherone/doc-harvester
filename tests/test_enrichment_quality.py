from __future__ import annotations

import pytest

from doc_harvester.core import Chunk, ContentBlock, ExtractedDocument, ResourceRef
from doc_harvester.enrichers import (
    BasicMetadataEnricher,
    available_enrichers,
    create_enricher,
)
from doc_harvester.quality import (
    BasicQualityGate,
    available_quality_gates,
    create_quality_gate,
)


def document(*blocks, filename="guide.md", extractor="text"):
    return ExtractedDocument(
        ResourceRef(filename, source="test", media_type="text/markdown"),
        tuple(blocks),
        metadata={
            "filename": filename,
            "media_type": "text/markdown",
            "extractor": extractor,
        },
    )


def test_basic_enricher_adds_neutral_document_and_chunk_metadata():
    source = document(
        ContentBlock("Installation", kind="heading", section="Installation"),
        ContentBlock("English and русский technical text.", section="Installation"),
    )
    chunks = [Chunk("English and русский technical text.", 0, {"token_count": 8})]

    result = BasicMetadataEnricher().enrich(source, chunks)

    assert result.document.metadata["source_type"] == "markdown"
    assert result.document.metadata["language"] == "mixed"
    assert result.document.metadata["document_class"] == "structured"
    assert result.document.metadata["block_count"] == 2
    assert result.document.metadata["char_count"] > 0
    assert len(result.document.metadata["content_sha256"]) == 64
    assert result.chunks[0].metadata["language"] == "mixed"
    assert result.chunks[0].metadata["document_language"] == "mixed"
    assert len(result.chunks[0].metadata["content_sha256"]) == 64
    assert "vendor" not in result.document.metadata
    assert "doc_type" not in result.chunks[0].metadata


def test_basic_enricher_classifies_table_majority_as_tabular():
    source = document(
        ContentBlock("Name | Rating", kind="table", section="Products"),
        ContentBlock("A-1 | 16 A", kind="table", section="Products"),
        filename="catalog.xlsx",
        extractor="xlsx",
    )

    result = BasicMetadataEnricher().enrich(source, [Chunk("A-1 | 16 A", 0)])

    assert result.document.metadata["source_type"] == "xlsx"
    assert result.document.metadata["document_class"] == "tabular"


def test_basic_enricher_uses_media_type_for_generic_filename():
    source = ExtractedDocument(
        ResourceRef(
            "download.bin",
            source="test",
            media_type="application/pdf",
        ),
        (ContentBlock("Embedded PDF text."),),
        metadata={
            "filename": "download.bin",
            "media_type": "application/pdf",
            "extractor": "pdf",
        },
    )

    result = BasicMetadataEnricher().enrich(source, [Chunk("Embedded PDF text.", 0)])

    assert result.document.metadata["source_type"] == "pdf"


def test_basic_quality_gate_passes_distinct_substantial_chunks():
    source = document(ContentBlock("Useful document content."))
    chunks = [
        Chunk(f"Distinct useful technical content number {index}. " * 8, index)
        for index in range(3)
    ]

    report = BasicQualityGate(min_tokens=5).evaluate(source, chunks)

    assert report.passed is True
    assert report.findings == ()
    assert report.metrics["total_chunks"] == 3


def test_basic_quality_gate_reports_tiny_duplicate_noisy_and_oversized_ratios():
    source = document(ContentBlock("Document content."))
    noisy = "(cid:1) (cid:2) (cid:3) (cid:4) (cid:5) (cid:6)"
    chunks = [
        Chunk("duplicate", 0, {"token_count": 1}),
        Chunk("duplicate", 1, {"token_count": 1}),
        Chunk(noisy, 2, {"token_count": 2, "oversized": True}),
    ]
    gate = BasicQualityGate(
        min_tokens=10,
        max_tiny_ratio=0.5,
        max_duplicate_ratio=0.0,
        max_noisy_ratio=0.0,
        max_oversized_ratio=0.0,
    )

    report = gate.evaluate(source, chunks)

    assert report.passed is False
    assert {finding.code for finding in report.findings} == {
        "tiny_ratio_exceeded",
        "duplicate_ratio_exceeded",
        "noisy_ratio_exceeded",
        "oversized_ratio_exceeded",
    }
    assert all(finding.severity == "warning" for finding in report.findings)


def test_basic_quality_gate_compares_unrounded_ratio_to_threshold():
    source = document(ContentBlock("Document content."))
    chunks = [
        Chunk("tiny", 0, {"token_count": 1}),
        Chunk("substantial useful content " * 20, 1, {"token_count": 20}),
        Chunk("different useful content " * 20, 2, {"token_count": 20}),
    ]

    report = BasicQualityGate(
        min_tokens=10,
        max_tiny_ratio=0.3333,
    ).evaluate(source, chunks)

    assert report.passed is False
    assert report.findings[0].code == "tiny_ratio_exceeded"
    assert report.metrics["ratios"]["tiny_ratio"] == pytest.approx(1 / 3)


def test_basic_quality_gate_rejects_missing_content():
    report = BasicQualityGate().evaluate(document(), [])

    assert report.passed is False
    assert report.findings[0].code == "missing_content"
    assert report.findings[0].severity == "error"


def test_enricher_and_quality_factories_are_public_and_validate_names():
    assert available_enrichers() == ("basic",)
    assert available_quality_gates() == ("basic",)
    assert isinstance(create_enricher("default"), BasicMetadataEnricher)
    assert isinstance(create_quality_gate("default"), BasicQualityGate)
    with pytest.raises(ValueError, match="unknown metadata enricher"):
        create_enricher("electrical")
    with pytest.raises(ValueError, match="unknown quality gate"):
        create_quality_gate("remote")


@pytest.mark.parametrize(
    "options",
    [
        {"min_tokens": 0},
        {"max_empty_ratio": -0.1},
        {"max_tiny_ratio": 1.1},
        {"max_duplicate_ratio": -1},
        {"max_noisy_ratio": 2},
        {"max_oversized_ratio": -0.01},
    ],
)
def test_basic_quality_gate_validates_thresholds(options):
    with pytest.raises(ValueError):
        BasicQualityGate(**options)
