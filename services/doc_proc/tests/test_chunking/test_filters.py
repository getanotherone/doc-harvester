"""Tests for chunk filters."""

from doc_proc.chunking.filters import apply_filters, is_metadata_row, is_ocr_garbage
from doc_proc.models import RawChunk


class TestMetadataFilter:
    def test_itogo_is_metadata(self):
        assert is_metadata_row("Итого по разделу: 15 000")

    def test_inn_is_metadata(self):
        assert is_metadata_row("ИНН: 7701234567 КПП: 770101001")

    def test_product_is_not_metadata(self):
        assert not is_metadata_row("Кабель ВВГнг(А)-LS 3×2.5 мм²")


class TestOCRGarbage:
    def test_normal_text_not_garbage(self):
        assert not is_ocr_garbage("Кабель ВВГнг 3×2.5 мм²")

    def test_garbage_detected(self):
        assert is_ocr_garbage("|||//\\\\....::::====----" * 3)

    def test_short_text_not_garbage(self):
        assert not is_ocr_garbage("||/")  # < 20 chars, skip


class TestApplyFilters:
    def test_removes_short_chunks(self):
        chunks = [
            RawChunk(text="Short", token_count=1),
            RawChunk(text="This is a long enough chunk of text for testing", token_count=12),
        ]
        result = apply_filters(chunks, min_text_length=10)
        assert len(result) == 1
        assert "long enough" in result[0].text

    def test_keeps_headings(self):
        chunks = [
            RawChunk(text="H", chunk_type="heading", token_count=1),
        ]
        result = apply_filters(chunks, min_text_length=10)
        assert len(result) == 1

    def test_removes_metadata(self):
        chunks = [
            RawChunk(text="Итого по разделу: 15 000 руб.", token_count=8),
            RawChunk(text="Кабель ВВГнг 3×2.5 мм² (01-001)", token_count=8),
        ]
        result = apply_filters(chunks, skip_metadata=True, min_text_length=5)
        assert len(result) == 1
        assert "Кабель" in result[0].text
