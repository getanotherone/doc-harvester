"""Fast text-based PDF parser using pdfplumber.

Handles text-based PDFs at ~100-200 pages/sec. Falls back to Docling/OCR
for scanned documents.
"""

from __future__ import annotations

import gc
import io
import logging
import re

from doc_proc.models import ParsedElement, ParseResult

logger = logging.getLogger(__name__)

PAGE_BATCH_SIZE = 100

_SECTION_NUM_RE = re.compile(
    r"^\s*(\d{1,3}[\.\)]\s+|[IVXLC]+[\.\)]\s+|Раздел\s+|Глава\s+)",
    re.IGNORECASE,
)
_ALL_CAPS_RE = re.compile(r"^[A-ZА-ЯЁ\s\d\-\.\,\(\)]{8,}$")


class PdfTextParser:
    """Parser for text-based PDFs using pdfplumber."""

    def can_handle(self, filename: str, content: bytes | None = None) -> bool:
        if not filename.lower().endswith(".pdf"):
            return False
        if content is not None:
            return self.is_text_based(content)
        return True

    def is_text_based(self, content: bytes) -> bool:
        """Check if PDF has extractable text by sampling pages."""
        try:
            import pdfplumber

            with pdfplumber.open(io.BytesIO(content)) as pdf:
                total = len(pdf.pages)
                if total == 0:
                    return False

                # Sample up to 5 pages evenly
                indices = [int(i * total / min(5, total)) for i in range(min(5, total))]
                text_pages = 0
                for idx in indices:
                    text = pdf.pages[idx].extract_text() or ""
                    if len(text.strip()) > 50:
                        text_pages += 1

                return text_pages > len(indices) * 0.5
        except Exception:
            return False

    def parse(self, content: bytes, filename: str) -> ParseResult:
        import pdfplumber

        elements: list[ParsedElement] = []
        element_idx = 0
        current_section = ""
        page_count = 0
        tables_count = 0

        with pdfplumber.open(io.BytesIO(content)) as pdf:
            page_count = len(pdf.pages)

            for page_num, page in enumerate(pdf.pages, start=1):
                # Find tables for exclusion
                tables = page.find_tables() or []
                tables_count += len(tables)

                # Extract text excluding table regions
                if tables:
                    table_bboxes = [t.bbox for t in tables]
                    filtered_page = page.filter(
                        lambda obj: not _in_any_bbox(obj, table_bboxes)
                    )
                    text = filtered_page.extract_text() or ""
                else:
                    text = page.extract_text() or ""

                # Process text lines
                for line in text.split("\n"):
                    line = line.strip()
                    if not line or len(line) < 3:
                        continue

                    if self._is_section_header(line):
                        current_section = line
                        el_type = "section_header"
                    else:
                        el_type = "data"

                    elements.append(ParsedElement(
                        index=element_idx,
                        text=line,
                        element_type=el_type,
                        section=current_section,
                        page=page_num,
                        row_type="section_header" if el_type == "section_header" else "text",
                    ))
                    element_idx += 1

                # Extract table rows
                for table in tables:
                    rows = table.extract() or []
                    for row in rows:
                        cells = [str(c).strip() if c else "" for c in row]
                        text_val = " | ".join(c for c in cells if c)
                        if not text_val.strip():
                            continue

                        elements.append(ParsedElement(
                            index=element_idx,
                            text=text_val,
                            element_type="data",
                            attributes={f"col_{i}": c for i, c in enumerate(cells) if c},
                            section=current_section,
                            page=page_num,
                            row_type="table_row",
                        ))
                        element_idx += 1

                # Periodic GC for large documents
                if page_num % PAGE_BATCH_SIZE == 0:
                    gc.collect()

        return ParseResult(
            elements=elements,
            format_hint="mixed" if tables_count > 0 else "document",
            document_type="pdf_text",
            page_count=page_count,
            tables_count=tables_count,
            has_ocr=False,
            metadata={"parser": "pdfplumber", "filename": filename},
        )

    def parse_from_path(self, path: str, filename: str) -> ParseResult:
        with open(path, "rb") as f:
            return self.parse(f.read(), filename)

    def _is_section_header(self, line: str) -> bool:
        """Detect section headers via numbering patterns or ALL CAPS."""
        if _SECTION_NUM_RE.match(line):
            return True
        if _ALL_CAPS_RE.match(line) and len(line) >= 10:
            alpha_ratio = sum(1 for c in line if c.isalpha()) / max(len(line), 1)
            return alpha_ratio >= 0.4
        return False


def _in_any_bbox(obj: dict, bboxes: list[tuple]) -> bool:
    """Check if a pdfplumber object falls inside any table bounding box."""
    if "top" not in obj or "x0" not in obj:
        return False
    for bbox in bboxes:
        x0, top, x1, bottom = bbox
        if x0 <= obj["x0"] <= x1 and top <= obj["top"] <= bottom:
            return True
    return False
