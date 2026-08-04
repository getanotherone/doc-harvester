"""Small dependency-free OOXML fixtures for DOCX extractor tests."""

from __future__ import annotations

from io import BytesIO
from zipfile import ZIP_DEFLATED, ZipFile


WORD_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"


def paragraph(text: str, *, style: str = "", numbered: bool = False) -> str:
    properties = ""
    if style or numbered:
        style_xml = f'<w:pStyle w:val="{style}"/>' if style else ""
        numbering_xml = "<w:numPr><w:ilvl w:val=\"0\"/><w:numId w:val=\"1\"/></w:numPr>" if numbered else ""
        properties = f"<w:pPr>{style_xml}{numbering_xml}</w:pPr>"
    return f"<w:p>{properties}<w:r><w:t>{text}</w:t></w:r></w:p>"


def table(*rows: tuple[str, ...]) -> str:
    rendered_rows = []
    for row in rows:
        cells = "".join(f"<w:tc>{paragraph(value)}</w:tc>" for value in row)
        rendered_rows.append(f"<w:tr>{cells}</w:tr>")
    return f"<w:tbl>{''.join(rendered_rows)}</w:tbl>"


def build_docx(
    body: str,
    *,
    include_content_types: bool = True,
    include_document: bool = True,
    extra_entries: dict[str, bytes] | None = None,
    word_namespace: str = WORD_NS,
) -> bytes:
    output = BytesIO()
    with ZipFile(output, "w", ZIP_DEFLATED) as archive:
        if include_content_types:
            archive.writestr(
                "[Content_Types].xml",
                "<?xml version=\"1.0\"?><Types "
                "xmlns=\"http://schemas.openxmlformats.org/package/2006/content-types\">"
                "<Override PartName=\"/word/document.xml\" "
                "ContentType=\"application/vnd.openxmlformats-officedocument."
                "wordprocessingml.document.main+xml\"/></Types>",
            )
        if include_document:
            archive.writestr(
                "word/document.xml",
                f'<?xml version="1.0"?><w:document xmlns:w="{word_namespace}">'
                f"<w:body>{body}<w:sectPr/></w:body></w:document>",
            )
        for name, content in (extra_entries or {}).items():
            archive.writestr(name, content)
    return output.getvalue()
