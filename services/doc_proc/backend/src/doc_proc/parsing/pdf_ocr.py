"""OCR-based PDF parser using Docling for scanned documents.

Handles scanned PDFs with Tesseract OCR (Russian+English), TableFormer
for table structure recovery, and layout analysis.
"""

from __future__ import annotations

import logging
import os
import tempfile

from doc_proc.models import ExtractedImage, ParsedElement, ParseResult

logger = logging.getLogger(__name__)


class PdfOcrParser:
    """Parser for scanned PDFs using Docling + Tesseract OCR."""

    def __init__(
        self,
        *,
        ocr_engine: str = "tesseract",
        ocr_languages: str = "rus+eng",
        table_mode: str = "fast",
        images_scale: float = 0.75,
    ):
        self.ocr_engine = ocr_engine
        self.ocr_languages = ocr_languages
        self.table_mode = table_mode
        self.images_scale = images_scale
        self._converter = None

    def can_handle(self, filename: str, content: bytes | None = None) -> bool:
        return filename.lower().endswith(".pdf")

    def parse(self, content: bytes, filename: str) -> ParseResult:
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
            tmp.write(content)
            tmp_path = tmp.name
        try:
            return self.parse_from_path(tmp_path, filename)
        finally:
            os.unlink(tmp_path)

    def parse_from_path(self, path: str, filename: str) -> ParseResult:
        converter = self._get_converter()
        result = converter.convert(path)
        doc = result.document

        elements: list[ParsedElement] = []
        images: list[ExtractedImage] = []
        element_idx = 0
        current_section = ""
        tables_count = 0

        from docling_core.types.doc import TableItem, TextItem

        for item, level in doc.iterate_items():
            if isinstance(item, TextItem):
                text = item.text.strip()
                if not text:
                    continue

                is_heading = level <= 2 or self._is_section_header(text, level)
                if is_heading:
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
                        page=getattr(item, "page_no", None),
                        row_type="table_row",
                    ))
                    element_idx += 1

        # Extract images
        from docling_core.types.doc import PictureItem

        img_idx = 0
        for item, _ in doc.iterate_items():
            if isinstance(item, PictureItem):
                img_data = self._picture_to_bytes(item)
                if img_data:
                    images.append(ExtractedImage(
                        index=img_idx,
                        image_data=img_data,
                        page=getattr(item, "page_no", None),
                        section=current_section,
                    ))
                    img_idx += 1

        return ParseResult(
            elements=elements,
            images=images,
            format_hint="document",
            document_type="pdf_ocr",
            page_count=getattr(doc, "page_count", 0) or 0,
            tables_count=tables_count,
            has_ocr=True,
            metadata={
                "parser": "docling",
                "ocr_engine": self.ocr_engine,
                "filename": filename,
            },
        )

    def _get_converter(self):
        """Lazy-initialize Docling converter with OCR settings."""
        if self._converter is not None:
            return self._converter

        from docling.datamodel.base_models import InputFormat
        from docling.datamodel.pipeline_options import (
            PdfPipelineOptions,
            TableFormerMode,
            TesseractCliOcrOptions,
        )
        from docling.document_converter import DocumentConverter, PdfFormatOption

        ocr_options = TesseractCliOcrOptions(
            lang=self.ocr_languages.split("+"),
            force_full_page_ocr=False,
        )

        table_mode = (
            TableFormerMode.ACCURATE
            if self.table_mode == "accurate"
            else TableFormerMode.FAST
        )

        pipeline_options = PdfPipelineOptions(
            do_ocr=self.ocr_engine != "none",
            ocr_options=ocr_options,
            do_table_structure=True,
            table_structure_options={"mode": table_mode},
            images_scale=self.images_scale,
            generate_page_images=False,
            generate_picture_images=False,
            generate_table_images=False,
        )

        self._converter = DocumentConverter(
            format_options={InputFormat.PDF: PdfFormatOption(pipeline_options=pipeline_options)}
        )
        return self._converter

    def _is_section_header(self, text: str, level: int) -> bool:
        """Check if text is a section header."""
        if level <= 2:
            return True
        section_kw = ("раздел", "глава", "часть", "система", "подраздел")
        lower = text.lower().strip()
        return any(lower.startswith(kw) for kw in section_kw)

    def _picture_to_bytes(self, item) -> bytes | None:
        """Extract image bytes from a Docling PictureItem."""
        try:
            img = item.get_image(None)
            if img is not None:
                import io
                buf = io.BytesIO()
                img.save(buf, format="PNG")
                return buf.getvalue()
        except Exception:
            pass

        try:
            if hasattr(item, "image") and item.image is not None:
                import io
                buf = io.BytesIO()
                item.image.save(buf, format="PNG")
                return buf.getvalue()
        except Exception:
            pass

        return None
