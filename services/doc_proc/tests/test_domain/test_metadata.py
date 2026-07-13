"""Tests for domain metadata extraction."""

from doc_proc.domain.metadata import detect_language, infer_metadata


class TestInferMetadata:
    def test_vendor_detection_abb(self):
        meta = infer_metadata("Автомат ABB S201 1P 16A", document_name="catalog.pdf")
        assert meta["vendor"] == "ABB"

    def test_vendor_detection_schneider(self):
        meta = infer_metadata("Schneider Electric iC60N", document_name="doc.pdf")
        assert meta["vendor"] == "Schneider"

    def test_vendor_detection_iek_cyrillic(self):
        meta = infer_metadata("Автомат ИЭК ВА47-29", document_name="doc.pdf")
        assert meta["vendor"] == "IEK"

    def test_no_vendor(self):
        meta = infer_metadata("Обычный кабель без вендора", document_name="doc.pdf")
        assert meta["vendor"] == ""

    def test_standard_id_gost(self):
        meta = infer_metadata("Соответствует ГОСТ 31996-2012", document_name="doc.pdf")
        assert "ГОСТ" in meta["standard_id"]
        assert "31996" in meta["standard_id"]

    def test_standard_id_iec(self):
        meta = infer_metadata("According to IEC 60947-2", document_name="doc.pdf")
        assert "IEC" in meta["standard_id"]

    def test_no_standard(self):
        meta = infer_metadata("Простой текст", document_name="doc.pdf")
        assert meta["standard_id"] == ""

    def test_year_from_standard(self):
        meta = infer_metadata("ГОСТ 31996-2012", document_name="doc.pdf")
        assert meta["year"] == 2012

    def test_doc_type_fire(self):
        meta = infer_metadata("Огнестойкий кабель для пожарной сигнализации")
        assert meta["doc_type"] == "fire"

    def test_doc_type_normative(self):
        meta = infer_metadata("Требования ГОСТ 31996-2012 к кабелям")
        assert meta["doc_type"] == "normative"

    def test_doc_type_catalog(self):
        meta = infer_metadata("Каталог продукции ABB 2024")
        assert meta["doc_type"] == "catalog"

    def test_doc_type_technical_default(self):
        meta = infer_metadata("Описание монтажа электропроводки")
        assert meta["doc_type"] == "technical"

    def test_source_type_from_extension(self):
        meta = infer_metadata("text", document_name="manual.pdf")
        assert meta["source_type"] == "pdf"

    def test_source_type_xlsx(self):
        meta = infer_metadata("text", document_name="data.xlsx")
        assert meta["source_type"] == "xlsx"

    def test_source_type_unknown(self):
        meta = infer_metadata("text", document_name="file.xyz")
        assert meta["source_type"] == "unknown"


class TestDetectLanguage:
    def test_russian(self):
        assert detect_language("Кабель силовой ВВГнг") == "ru"

    def test_english(self):
        assert detect_language("Power cable specifications") == "en"

    def test_mixed(self):
        assert detect_language("Кабель ABB Power Cable") == "mixed"

    def test_unknown(self):
        assert detect_language("12345 +-*/") == "unknown"
