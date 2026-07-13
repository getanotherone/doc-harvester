"""Tests for Excel parser."""

import pytest

from doc_proc.parsing.excel import ExcelParser


class TestExcelParser:
    def test_can_handle(self):
        parser = ExcelParser()
        assert parser.can_handle("test.xlsx")
        assert parser.can_handle("test.xls")
        assert parser.can_handle("test.csv")
        assert not parser.can_handle("test.pdf")

    def test_classify_row_data(self):
        parser = ExcelParser()
        assert parser._classify_row(["1", "01-001", "Кабель ВВГ", "м", "100"]) == "data"

    def test_classify_row_section_header(self):
        parser = ExcelParser()
        assert parser._classify_row(["Раздел 1. Электроснабжение", "", ""]) == "section_header"

    def test_classify_row_subtotal(self):
        parser = ExcelParser()
        assert parser._classify_row(["", "Итого по разделу", "1500.00"]) == "subtotal"

    def test_classify_row_column_number(self):
        parser = ExcelParser()
        assert parser._classify_row(["1", "2", "3", "4", "5"]) == "column_number"

    def test_build_semantic_raw_text_full(self):
        parser = ExcelParser()
        attrs = {"name": "Кабель ВВГнг 3×2.5", "code": "01-001", "unit": "м", "quantity": "100"}
        result = parser._build_semantic_raw_text(attrs, [])
        assert "Кабель ВВГнг 3×2.5" in result
        assert "(01-001)" in result
        assert "100 м" in result

    def test_build_semantic_raw_text_name_only(self):
        parser = ExcelParser()
        attrs = {"name": "Кабель ВВГнг 3×2.5"}
        result = parser._build_semantic_raw_text(attrs, [])
        assert result == "Кабель ВВГнг 3×2.5"

    def test_build_semantic_raw_text_fallback(self):
        parser = ExcelParser()
        attrs = {"col_0": "value1", "col_1": "value2"}
        result = parser._build_semantic_raw_text(attrs, ["val1", "val2", "val3"])
        assert len(result) > 0

    def test_match_header_row(self):
        parser = ExcelParser()
        row = ("№ п/п", "Обоснование", "Наименование", "Ед. изм.", "Количество")
        score, mapping = parser._match_header_row(row)
        assert score >= 4
        assert "name" in mapping
        assert "code" in mapping
        assert "unit" in mapping
