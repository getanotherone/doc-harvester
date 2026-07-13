"""Tests for data models."""

from doc_proc.models import estimate_tokens, ParsedElement, RawChunk, ParseResult


class TestEstimateTokens:
    def test_basic(self):
        tokens = estimate_tokens("hello world")
        assert 1 <= tokens <= 5  # tiktoken: 2, fallback: 2-3

    def test_empty(self):
        assert estimate_tokens("") == 1  # min 1

    def test_russian(self):
        text = "Кабель силовой ВВГнг(А)-LS"
        tokens = estimate_tokens(text)
        assert tokens > 3


class TestParsedElement:
    def test_defaults(self):
        el = ParsedElement(0, "test", "data")
        assert el.section == ""
        assert el.page is None
        assert el.confidence == 1.0


class TestRawChunk:
    def test_defaults(self):
        chunk = RawChunk(text="test")
        assert chunk.chunk_type == "text"
        assert chunk.section == ""
        assert chunk.token_count == 0


class TestParseResult:
    def test_format_hint(self):
        pr = ParseResult(elements=[], format_hint="tabular")
        assert pr.format_hint == "tabular"
        assert pr.document_type == "unknown"
