"""Tests for the Pipeline orchestrator."""

import pytest

from doc_proc.models import ParseResult, ParsedElement
from doc_proc.pipeline import Pipeline, PipelineConfig


class TestPipeline:
    def test_chunk_tabular(self, sample_tabular_parse_result):
        config = PipelineConfig(strategy="auto", embed=False)
        pipeline = Pipeline(config)
        result = pipeline.chunk(sample_tabular_parse_result)
        assert len(result.chunks) > 0
        assert result.strategy_used in ("hierarchical", "row_level")

    def test_chunk_document(self, sample_document_parse_result):
        config = PipelineConfig(strategy="auto", embed=False)
        pipeline = Pipeline(config)
        result = pipeline.chunk(sample_document_parse_result)
        assert len(result.chunks) > 0
        assert result.strategy_used == "structure_aware"

    def test_explicit_strategy(self, sample_tabular_parse_result):
        config = PipelineConfig(strategy="row_level", embed=False)
        pipeline = Pipeline(config)
        result = pipeline.chunk(sample_tabular_parse_result)
        assert result.strategy_used == "row_level"

    def test_evaluate(self, sample_tabular_parse_result):
        config = PipelineConfig(strategy="hierarchical", embed=False)
        pipeline = Pipeline(config)
        chunk_result = pipeline.chunk(sample_tabular_parse_result)
        quality = pipeline.evaluate(chunk_result)
        assert quality.total_chunks > 0
        assert quality.avg_tokens > 0

    def test_filter_removes_noise(self):
        elements = [
            ParsedElement(0, "Кабель ВВГнг 3×2.5 мм²", "data"),
            ParsedElement(1, "+7 (495) 123-45-67", "data"),
        ]
        pr = ParseResult(elements=elements, format_hint="document")
        config = PipelineConfig(content_filter=True, embed=False)
        pipeline = Pipeline(config)
        filtered = pipeline.filter(pr)
        assert len(filtered.elements) == 1  # Phone removed

    def test_context_injection(self, sample_tabular_parse_result):
        config = PipelineConfig(
            strategy="row_level",
            inject_context=True,
            doc_title="КСР.xlsx",
            embed=False,
        )
        pipeline = Pipeline(config)
        result = pipeline.chunk(sample_tabular_parse_result)
        assert any("КСР.xlsx" in c.text for c in result.chunks)
