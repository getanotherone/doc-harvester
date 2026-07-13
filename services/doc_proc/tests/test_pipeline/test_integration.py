"""Integration coverage for the local document-processing pipeline."""

import asyncio
import io

from openpyxl import Workbook

from doc_proc.pipeline import Pipeline, PipelineConfig


def _electrical_catalogue() -> bytes:
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Catalogue"
    sheet.append(["Код ресурса", "Наименование", "Ед. изм", "Количество"])
    sheet.append(["01-001", "Кабель ВВГнг 3x2.5 мм2", "м", 100])
    sheet.append(["01-002", "Автоматический выключатель ВА47-29 16А", "шт", 4])
    sheet.append(["", "+7 (495) 123-45-67", "", ""])

    output = io.BytesIO()
    workbook.save(output)
    workbook.close()
    return output.getvalue()


def test_xlsx_pipeline_contract():
    """An XLSX catalogue is parsed, cleaned, chunked, enriched, and evaluated."""
    pipeline = Pipeline(
        PipelineConfig(
            strategy="auto",
            content_filter=True,
            doc_title="electrical-catalogue.xlsx",
            embed=False,
        )
    )

    chunks, embeddings, quality = asyncio.run(
        pipeline.run(_electrical_catalogue(), "electrical-catalogue.xlsx")
    )

    combined_text = "\n".join(chunk.text for chunk in chunks.chunks)
    assert chunks.strategy_used == "row_level"
    assert embeddings is None
    assert quality.total_chunks == 2
    assert quality.total_tokens > 0
    assert "Кабель ВВГнг" in combined_text
    assert "Автоматический выключатель" in combined_text
    assert "123-45-67" not in combined_text
    assert all(chunk.source_type == "xlsx" for chunk in chunks.chunks)
