"""Small in-memory XLSX fixtures for extractor tests."""

from __future__ import annotations

from io import BytesIO

from openpyxl import Workbook


def build_xlsx(
    sheets: dict[str, list[list[object]]],
    *,
    hidden_sheets: set[str] | None = None,
    very_hidden_sheets: set[str] | None = None,
) -> bytes:
    workbook = Workbook()
    workbook.remove(workbook.active)
    try:
        for title, rows in sheets.items():
            worksheet = workbook.create_sheet(title)
            for row in rows:
                worksheet.append(row)
            if title in (hidden_sheets or set()):
                worksheet.sheet_state = "hidden"
            if title in (very_hidden_sheets or set()):
                worksheet.sheet_state = "veryHidden"
        output = BytesIO()
        workbook.save(output)
        return output.getvalue()
    finally:
        workbook.close()
