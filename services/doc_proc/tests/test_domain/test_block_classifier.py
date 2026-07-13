"""Tests for block type classification."""

from doc_proc.domain.block_classifier import classify_block, is_normative_block, is_table_like


class TestIsTableLike:
    def test_pipe_separated_is_table(self):
        text = "Наименование | Кол-во | Ед.\nКабель ВВГнг | 100 | м\nАвтомат ВА47 | 5 | шт"
        assert is_table_like(text)

    def test_tab_separated_is_table(self):
        text = "Наименование\tКол-во\tЕд.\nКабель ВВГнг\t100\tм\nАвтомат ВА47\t5\tшт"
        assert is_table_like(text)

    def test_regular_paragraph_not_table(self):
        text = "Стабилизаторы предназначены для поддержания напряжения в сети."
        assert not is_table_like(text)

    def test_single_line_not_table(self):
        assert not is_table_like("Кабель ВВГнг 3x2.5")

    def test_column_space_alignment(self):
        text = "\n".join([
            "Наименование      Кол-во     Ед.",
            "Кабель ВВГнг      100        м",
            "Автомат ВА47      5          шт",
            "Розетка           10         шт",
            "Выключатель       15         шт",
        ])
        assert is_table_like(text)

    def test_code_and_numeric_lines(self):
        text = "\n".join([
            "АВ-001",
            "100",
            "АВ-002",
            "200",
            "АВ-003",
            "300",
            "АВ-004",
            "400",
        ])
        assert is_table_like(text)


class TestIsNormativeBlock:
    def test_numbered_paragraph(self):
        assert is_normative_block("1.2.3 Требования к прокладке кабелей")

    def test_letter_item(self):
        assert is_normative_block("а) первое требование")

    def test_roman_numeral(self):
        assert is_normative_block("III. Раздел три")

    def test_regular_text_not_normative(self):
        assert not is_normative_block("Кабель ВВГнг предназначен для...")


class TestClassifyBlock:
    def test_normal_text(self):
        assert classify_block("Обычный текст документа.") == ["normal"]

    def test_normative_block(self):
        labels = classify_block("1.2 Требования к монтажу")
        assert "normative" in labels

    def test_table_block(self):
        text = "A | B | C\n1 | 2 | 3\n4 | 5 | 6"
        labels = classify_block(text)
        assert "table" in labels
