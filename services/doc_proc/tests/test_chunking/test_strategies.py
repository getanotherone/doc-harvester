"""Tests for chunking strategies."""

import pytest

from doc_proc.chunking.strategies.hierarchical import HierarchicalChunker
from doc_proc.chunking.strategies.row_level import RowLevelChunker
from doc_proc.chunking.strategies.row_group import RowGroupChunker
from doc_proc.chunking.strategies.structure_aware import StructureAwareChunker
from doc_proc.chunking.strategies.semantic import SemanticChunker
from doc_proc.chunking.registry import auto_select, get_chunker, list_strategies
from doc_proc.models import ParseResult, ParsedElement


class TestHierarchicalChunker:
    def test_basic_chunking(self, sample_tabular_parse_result):
        chunker = HierarchicalChunker()
        result = chunker.chunk(sample_tabular_parse_result)
        assert len(result.chunks) > 0
        assert result.strategy_used == "hierarchical"

    def test_section_boundaries(self, sample_tabular_parse_result):
        chunker = HierarchicalChunker()
        result = chunker.chunk(sample_tabular_parse_result, group_size=100)
        sections = {c.section for c in result.chunks}
        assert len(sections) >= 1

    def test_empty_input(self):
        chunker = HierarchicalChunker()
        result = chunker.chunk(ParseResult(elements=[], format_hint="tabular"))
        assert len(result.chunks) == 0


class TestRowLevelChunker:
    def test_one_per_row(self, sample_tabular_parse_result):
        chunker = RowLevelChunker()
        result = chunker.chunk(sample_tabular_parse_result)
        # Should have 5 data rows (excluding 2 section headers)
        assert len(result.chunks) == 5
        assert result.strategy_used == "row_level"

    def test_preserves_attributes(self, sample_tabular_parse_result):
        chunker = RowLevelChunker()
        result = chunker.chunk(sample_tabular_parse_result)
        assert any(c.metadata.get("code") for c in result.chunks)


class TestRowGroupChunker:
    def test_grouping(self, sample_tabular_parse_result):
        chunker = RowGroupChunker()
        result = chunker.chunk(sample_tabular_parse_result, group_size=2)
        assert len(result.chunks) >= 2  # At least 2 groups
        assert result.strategy_used == "row_group"


class TestStructureAwareChunker:
    def test_heading_groups(self, sample_document_parse_result):
        chunker = StructureAwareChunker()
        result = chunker.chunk(sample_document_parse_result)
        assert len(result.chunks) > 0
        assert result.strategy_used == "structure_aware"

    def test_table_gets_higher_limit(self, sample_document_parse_result):
        chunker = StructureAwareChunker()
        result = chunker.chunk(sample_document_parse_result)
        # Should handle both text and table elements
        types = {c.chunk_type for c in result.chunks}
        assert len(types) >= 1


class TestSemanticChunker:
    def test_pattern_splitting(self):
        text = "Раздел 1. Кабели\nТекст раздела 1\n\nРаздел 2. Автоматы\nТекст раздела 2\n\nРаздел 3. Шины\nТекст раздела 3"
        elements = [ParsedElement(0, text, "text")]
        pr = ParseResult(elements=elements, format_hint="document")
        chunker = SemanticChunker()
        result = chunker.chunk(pr)
        assert len(result.chunks) >= 2
        assert result.strategy_used == "semantic"


class TestRegistry:
    def test_auto_select_tabular(self, sample_tabular_parse_result):
        strategy = auto_select(sample_tabular_parse_result)
        assert strategy in ("hierarchical", "row_level")

    def test_auto_select_document(self, sample_document_parse_result):
        strategy = auto_select(sample_document_parse_result)
        assert strategy == "structure_aware"

    def test_get_chunker_valid(self):
        chunker = get_chunker("hierarchical")
        assert chunker.name == "hierarchical"

    def test_get_chunker_invalid(self):
        with pytest.raises(ValueError, match="Unknown strategy"):
            get_chunker("nonexistent")

    def test_list_strategies(self):
        strategies = list_strategies()
        names = [s["name"] for s in strategies]
        assert "hierarchical" in names
        assert "row_level" in names
        assert "structure_aware" in names
