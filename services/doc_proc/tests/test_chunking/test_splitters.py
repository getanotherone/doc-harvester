"""Tests for text splitting utilities."""

from doc_proc.chunking.splitters import split_text, split_table_markdown


class TestSplitText:
    def test_short_text_no_split(self):
        result = split_text("Short text", max_tokens=100)
        assert len(result) == 1
        assert result[0] == "Short text"

    def test_splits_long_text(self):
        text = "Word " * 1000  # ~5000 chars
        result = split_text(text, max_tokens=128)  # 512 chars
        assert len(result) > 1
        for part in result:
            assert len(part) <= 600  # Some tolerance

    def test_prefers_newline_breaks(self):
        text = "Line one\nLine two\nLine three\nLine four"
        result = split_text(text, max_tokens=5)  # ~20 chars
        for part in result:
            # Should not split mid-line
            assert not part.startswith(" ")

    def test_empty_text(self):
        result = split_text("")
        assert result == []


class TestSplitTableMarkdown:
    def test_header_repeated(self):
        table = "Name | Code\n---|---\nRow 1 | A\nRow 2 | B\nRow 3 | C"
        result = split_table_markdown(table, max_tokens=5)
        for part in result:
            assert "Name | Code" in part

    def test_small_table_no_split(self):
        table = "Name | Code\n---|---\nRow 1 | A"
        result = split_table_markdown(table, max_tokens=100)
        assert len(result) == 1
