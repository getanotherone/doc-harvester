"""Tests for Stage 3 minimal model output."""

from doc_proc.domain.stage3_output import to_stage3_minimal


def test_all_fields_present():
    result = to_stage3_minimal(
        text="Кабель ВВГнг 3x2.5",
        document="cable_catalog.pdf",
        page=5,
        section="1.2 Силовые кабели",
        chunk_index=42,
        doc_type="catalog",
        vendor="ABB",
        standard_id="ГОСТ 31996-2012",
        year=2012,
        lang="ru",
        source_type="pdf",
        quality_status="pass",
    )
    assert result["document"] == "cable_catalog.pdf"
    assert result["page"] == 5
    assert result["section"] == "1.2 Силовые кабели"
    assert result["chunk_index"] == 42
    assert result["text"] == "Кабель ВВГнг 3x2.5"
    assert result["doc_type"] == "catalog"
    assert result["vendor"] == "ABB"
    assert result["standard_id"] == "ГОСТ 31996-2012"
    assert result["year"] == 2012
    assert result["lang"] == "ru"
    assert result["source_type"] == "pdf"
    assert result["quality_status"] == "pass"


def test_defaults():
    result = to_stage3_minimal(text="test")
    assert result["document"] == ""
    assert result["page"] == 0
    assert result["section"] == ""
    assert result["chunk_index"] == 0
    assert result["doc_type"] == "technical"
    assert result["vendor"] == ""
    assert result["standard_id"] == ""
    assert result["year"] is None
    assert result["lang"] == "unknown"
    assert result["source_type"] == "unknown"
    assert result["quality_status"] == "unknown"


def test_schema_has_12_fields():
    result = to_stage3_minimal(text="test")
    assert len(result) == 12
