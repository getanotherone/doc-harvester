"""Tests for content noise filter."""

from doc_proc.parsing.filters.content import classify_content


class TestContentFilter:
    def test_phone_is_noise(self):
        result = classify_content("+7 (495) 123-45-67")
        assert result.label == "noise"

    def test_legal_entity_is_noise(self):
        result = classify_content("ООО «СтройМонтаж» ИНН 7701234567")
        assert result.label == "noise"

    def test_product_is_valuable(self):
        result = classify_content("Кабель ВВГнг(А)-LS 3×2.5 мм²")
        assert result.label == "valuable"

    def test_gost_is_valuable(self):
        result = classify_content("Изготовлен по ГОСТ 31996-2012")
        assert result.label == "valuable"

    def test_page_number_is_noise(self):
        result = classify_content("  42  ")
        assert result.label == "noise"

    def test_mixed_content_classified(self):
        # Technical content with some noise
        result = classify_content("Автомат ВА47-29 1P 16А IP20")
        assert result.label == "valuable"
