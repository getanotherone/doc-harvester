from __future__ import annotations

from datetime import date
from io import BytesIO
from zipfile import ZIP_DEFLATED, ZipFile

import pytest

from doc_harvester.chunkers import StructureAwareChunker
from doc_harvester.core import ChunkingOptions, FetchedArtifact, ResourceRef
from doc_harvester.extractors import XLSXExtractor, select_extractor
from tests.xlsx_fixture import build_xlsx


MEDIA_TYPE = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def artifact(content: bytes, *, filename: str = "catalog.xlsx") -> FetchedArtifact:
    resource = ResourceRef(filename, source="test", media_type=MEDIA_TYPE)
    return FetchedArtifact(resource, content, media_type=MEDIA_TYPE, filename=filename)


def test_xlsx_extractor_preserves_sheets_rows_values_and_formulas():
    source = artifact(
        build_xlsx(
            {
                "Catalog": [
                    ["Name", "Value", "Active"],
                    ["Pump", "=SUM(1,2)", True],
                    ["Released", date(2026, 8, 4), "A | B"],
                    [None, None, None],
                ]
            }
        )
    )

    document = XLSXExtractor().extract(source)

    assert [block.text for block in document.blocks] == [
        "Name | Value | Active",
        "Pump | =SUM(1,2) | TRUE",
        "Released | 2026-08-04T00:00:00 | A \\| B",
    ]
    assert all(block.kind == "table" for block in document.blocks)
    assert all(block.section == "Catalog" for block in document.blocks)
    assert document.blocks[1].metadata == {
        "sheet": "Catalog",
        "sheet_index": 0,
        "sheet_state": "visible",
        "row": 2,
        "columns": 3,
        "non_empty_cells": 3,
        "formula_cells": 1,
    }
    assert document.metadata == {
        "extractor": "xlsx",
        "filename": "catalog.xlsx",
        "media_type": MEDIA_TYPE,
        "sheet_count": 1,
        "processed_sheet_count": 1,
        "skipped_hidden_sheet_count": 0,
        "row_count": 4,
        "nonempty_row_count": 3,
        "cell_count": 12,
        "block_count": 3,
        "formula_count": 1,
        "formulas_evaluated": False,
    }

    chunks = StructureAwareChunker().chunk(
        document,
        ChunkingOptions(strategy="structure-aware", max_tokens=100, overlap_tokens=0),
    )
    assert chunks[0].metadata["section"] == "Catalog"
    assert chunks[0].metadata["page"] is None
    assert chunks[0].metadata["start_page"] is None
    assert chunks[0].metadata["end_page"] is None
    assert "table" in chunks[0].metadata["block_types"]


def test_xlsx_extractor_excludes_hidden_sheets_by_default_and_allows_opt_in():
    content = build_xlsx(
        {
            "Public": [["Visible"]],
            "Internal": [["Hidden value"]],
            "Secrets": [["Very hidden value"]],
        },
        hidden_sheets={"Internal"},
        very_hidden_sheets={"Secrets"},
    )

    default_document = XLSXExtractor().extract(artifact(content))
    included_document = XLSXExtractor(include_hidden_sheets=True).extract(artifact(content))

    assert [block.text for block in default_document.blocks] == ["Visible"]
    assert default_document.metadata["skipped_hidden_sheet_count"] == 2
    assert "Internal" not in str(default_document.metadata)
    assert [block.text for block in included_document.blocks] == [
        "Visible",
        "Hidden value",
        "Very hidden value",
    ]


def test_xlsx_factory_selection_forwards_safety_and_hidden_sheet_policy():
    selected = select_extractor(
        artifact(build_xlsx({"Data": [["Text"]]})),
        max_xlsx_sheets=7,
        max_xlsx_rows=8,
        max_xlsx_cells=9,
        max_xlsx_uncompressed_bytes=12_345,
        include_hidden_xlsx_sheets=True,
    )

    assert isinstance(selected, XLSXExtractor)
    assert selected.max_sheets == 7
    assert selected.max_rows == 8
    assert selected.max_cells == 9
    assert selected.max_uncompressed_bytes == 12_345
    assert selected.include_hidden_sheets is True


def test_xlsx_extractor_enforces_sheet_row_cell_entry_and_expansion_limits():
    content = artifact(build_xlsx({"One": [["A", "B"], ["C", "D"]], "Two": [["E"]]}))

    for options, message in (
        ({"max_sheets": 1}, "sheet limit"),
        ({"max_rows": 1}, "row limit"),
        ({"max_cells": 1}, "cell limit"),
        ({"max_entries": 1}, "entry limit"),
        ({"max_uncompressed_bytes": 10}, "uncompressed-byte limit"),
    ):
        with pytest.raises(ValueError, match=message):
            XLSXExtractor(**options).extract(content)


@pytest.mark.parametrize(
    ("content", "message"),
    [
        (b"not an XLSX", "signature"),
        (b"PK broken", "extraction failed"),
    ],
)
def test_xlsx_extractor_rejects_invalid_containers_safely(content, message):
    with pytest.raises(ValueError, match=message):
        XLSXExtractor().extract(artifact(content))


def test_xlsx_extractor_rejects_missing_required_parts():
    output = BytesIO()
    with ZipFile(output, "w", ZIP_DEFLATED) as archive:
        archive.writestr("[Content_Types].xml", b"<Types/>")

    with pytest.raises(ValueError, match="missing required"):
        XLSXExtractor().extract(artifact(output.getvalue()))
