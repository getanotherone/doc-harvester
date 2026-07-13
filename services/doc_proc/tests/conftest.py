"""Shared test fixtures."""

import pytest

from doc_proc.embedding.fake import FakeEmbeddingProvider
from doc_proc.models import ParseResult, ParsedElement


@pytest.fixture
def fake_embedder():
    return FakeEmbeddingProvider(dimension=1024)


@pytest.fixture
def sample_tabular_elements():
    """Sample parsed elements from an Excel file."""
    return [
        ParsedElement(0, "КАБЕЛИ СИЛОВЫЕ", "section_header", section=""),
        ParsedElement(1, "Кабель ВВГнг 3×2.5 (01-001)", "data", {"name": "Кабель ВВГнг 3×2.5", "code": "01-001"}, "КАБЕЛИ СИЛОВЫЕ"),
        ParsedElement(2, "Кабель ВВГнг 3×4.0 (01-002)", "data", {"name": "Кабель ВВГнг 3×4.0", "code": "01-002"}, "КАБЕЛИ СИЛОВЫЕ"),
        ParsedElement(3, "Кабель АСБ 3×185 10кВ (01-003)", "data", {"name": "Кабель АСБ 3×185 10кВ", "code": "01-003"}, "КАБЕЛИ СИЛОВЫЕ"),
        ParsedElement(4, "АВТОМАТИЧЕСКИЕ ВЫКЛЮЧАТЕЛИ", "section_header", section=""),
        ParsedElement(5, "Автомат ВА47-29 1P 16А (02-001)", "data", {"name": "Автомат ВА47-29 1P 16А", "code": "02-001"}, "АВТОМАТИЧЕСКИЕ ВЫКЛЮЧАТЕЛИ"),
        ParsedElement(6, "Автомат ВА47-29 3P 25А (02-002)", "data", {"name": "Автомат ВА47-29 3P 25А", "code": "02-002"}, "АВТОМАТИЧЕСКИЕ ВЫКЛЮЧАТЕЛИ"),
    ]


@pytest.fixture
def sample_tabular_parse_result(sample_tabular_elements):
    return ParseResult(
        elements=sample_tabular_elements,
        format_hint="tabular",
        document_type="spreadsheet",
    )


@pytest.fixture
def sample_document_elements():
    """Sample parsed elements from a PDF document."""
    return [
        ParsedElement(0, "1. Стабилизаторы напряжения", "heading", page=1),
        ParsedElement(1, "Стабилизаторы предназначены для поддержания напряжения в сети.", "text", page=1, section="1. Стабилизаторы напряжения"),
        ParsedElement(2, "Модель СНР-5000 | Мощность 5кВА | Напряжение 220В", "data", page=1, section="1. Стабилизаторы напряжения", row_type="table_row"),
        ParsedElement(3, "2. Источники бесперебойного питания", "heading", page=2),
        ParsedElement(4, "ИБП обеспечивает автономное питание оборудования при отключении электроэнергии.", "text", page=2, section="2. Источники бесперебойного питания"),
    ]


@pytest.fixture
def sample_document_parse_result(sample_document_elements):
    return ParseResult(
        elements=sample_document_elements,
        format_hint="document",
        document_type="pdf_text",
        page_count=3,
    )
