"""Tests for row quality grading."""

from doc_proc.parsing.filters.grade import calculate_grade


class TestGrade:
    def test_empty_attributes(self):
        assert calculate_grade({}) == 0.0

    def test_high_value_fields(self):
        attrs = {"name": "Кабель ВВГнг 3×2.5", "code": "01-001"}
        grade = calculate_grade(attrs)
        assert grade > 0.5

    def test_unit_detection(self):
        attrs = {"name": "Труба", "unit": "м", "quantity": "10"}
        grade = calculate_grade(attrs)
        assert grade > 0.4

    def test_code_detection(self):
        attrs = {"code": "01.7.15.03-0042"}
        grade = calculate_grade(attrs)
        assert grade > 0.4

    def test_low_value_unnamed(self):
        attrs = {"col_0": "1", "col_1": "2"}
        grade = calculate_grade(attrs)
        assert grade < 0.5
