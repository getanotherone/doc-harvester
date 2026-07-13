"""DOCX/PPTX parser using Docling."""

from __future__ import annotations

import logging
import os
import tempfile

from doc_proc.models import ParsedElement, ParseResult

logger = logging.getLogger(__name__)


class DocxParser:
    """Parser for DOCX and PPTX files using Docling."""

    def can_handle(self, filename: str, content: bytes | None = None) -> bool:
        ext = filename.rsplit(".", 1)[-1].lower()
        return ext in ("docx", "pptx")

    def parse(self, content: bytes, filename: str) -> ParseResult:
        ext = filename.rsplit(".", 1)[-1].lower()
        suffix = f".{ext}"

        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
            tmp.write(content)
            tmp_path = tmp.name

        try:
            return self.parse_from_path(tmp_path, filename)
        finally:
            os.unlink(tmp_path)

    def parse_from_path(self, path: str, filename: str) -> ParseResult:
        from docling.document_converter import DocumentConverter

        converter = DocumentConverter()
        result = converter.convert(path)
        doc = result.document

        elements: list[ParsedElement] = []
        element_idx = 0
        current_section = ""
        tables_count = 0

        from docling_core.types.doc import TableItem, TextItem

        for item, level in doc.iterate_items():
            if isinstance(item, TextItem):
                text = item.text.strip()
                if not text:
                    continue

                if level <= 2:
                    current_section = text
                    el_type = "heading"
                else:
                    el_type = "text"

                elements.append(ParsedElement(
                    index=element_idx,
                    text=text,
                    element_type=el_type,
                    section=current_section,
                    page=getattr(item, "page_no", None),
                ))
                element_idx += 1

            elif isinstance(item, TableItem):
                tables_count += 1
                md = item.export_to_markdown()
                if md.strip():
                    elements.append(ParsedElement(
                        index=element_idx,
                        text=md,
                        element_type="data",
                        section=current_section,
                        row_type="table_row",
                    ))
                    element_idx += 1

        return ParseResult(
            elements=elements,
            format_hint="document",
            document_type="docx",
            tables_count=tables_count,
            metadata={"parser": "docling", "filename": filename},
        )
