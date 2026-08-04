"""Structure-preserving DOCX extractor using the OOXML container format."""

from __future__ import annotations

from io import BytesIO
from urllib.parse import urlsplit
from xml.etree import ElementTree
from zipfile import ZipFile

from chunker import normalize_text
from doc_harvester.core import ContentBlock, ExtractedDocument, Extractor, FetchedArtifact


_WORD_NAMESPACES = {
    "http://schemas.openxmlformats.org/wordprocessingml/2006/main",
    "http://purl.oclc.org/ooxml/wordprocessingml/main",
}


class _DOCXValidationError(Exception):
    pass


class DOCXExtractor(Extractor):
    """Extract main-body paragraphs, headings, lists, and table rows from DOCX bytes."""

    name = "docx"
    _MEDIA_TYPES = {
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    }
    _DOCUMENT_PATH = "word/document.xml"
    _CONTENT_TYPES_PATH = "[Content_Types].xml"

    def __init__(
        self,
        *,
        max_blocks: int = 10_000,
        max_entries: int = 2_000,
        max_uncompressed_bytes: int = 100 * 1024 * 1024,
        max_document_xml_bytes: int = 20 * 1024 * 1024,
    ) -> None:
        for name, value in (
            ("DOCX max blocks", max_blocks),
            ("DOCX max entries", max_entries),
            ("DOCX max uncompressed bytes", max_uncompressed_bytes),
            ("DOCX max document XML bytes", max_document_xml_bytes),
        ):
            if value < 1:
                raise ValueError(f"{name} must be at least 1")
        self.max_blocks = max_blocks
        self.max_entries = max_entries
        self.max_uncompressed_bytes = max_uncompressed_bytes
        self.max_document_xml_bytes = max_document_xml_bytes

    def supports(self, artifact: FetchedArtifact) -> bool:
        media_type = artifact.media_type.split(";", 1)[0].strip().lower()
        candidate = artifact.filename or urlsplit(artifact.resource.uri).path
        return media_type in self._MEDIA_TYPES or candidate.lower().endswith(".docx")

    def extract(self, artifact: FetchedArtifact) -> ExtractedDocument:
        if not self.supports(artifact):
            raise ValueError(f"{self.name} extractor does not support this artifact")
        if not artifact.content.startswith(b"PK"):
            raise ValueError("invalid DOCX container signature")

        try:
            xml_payload = self._read_document_xml(artifact.content)
            root, word_prefix = self._parse_document_xml(xml_payload)
            blocks, counts = self._extract_blocks(root, word_prefix)
        except _DOCXValidationError as error:
            raise ValueError(str(error)) from None
        except Exception as error:
            raise ValueError(f"DOCX extraction failed: {type(error).__name__}") from None

        return ExtractedDocument(
            artifact.resource,
            tuple(blocks),
            metadata={
                "extractor": self.name,
                "filename": artifact.filename,
                "media_type": artifact.media_type,
                **counts,
            },
        )

    def _read_document_xml(self, content: bytes) -> bytes:
        with ZipFile(BytesIO(content)) as archive:
            entries = archive.infolist()
            if len(entries) > self.max_entries:
                raise _DOCXValidationError(
                    f"DOCX exceeds configured entry limit ({self.max_entries})"
                )
            if sum(entry.file_size for entry in entries) > self.max_uncompressed_bytes:
                raise _DOCXValidationError(
                    "DOCX exceeds configured uncompressed-byte limit "
                    f"({self.max_uncompressed_bytes})"
                )
            if any(entry.flag_bits & 0x1 for entry in entries):
                raise _DOCXValidationError("encrypted DOCX entries are not supported")

            names = [entry.filename for entry in entries]
            if self._CONTENT_TYPES_PATH not in names or self._DOCUMENT_PATH not in names:
                raise _DOCXValidationError("DOCX is missing required OOXML parts")
            if names.count(self._DOCUMENT_PATH) != 1:
                raise _DOCXValidationError("DOCX contains duplicate main document parts")

            document_info = archive.getinfo(self._DOCUMENT_PATH)
            if document_info.file_size > self.max_document_xml_bytes:
                raise _DOCXValidationError(
                    "DOCX main document exceeds configured XML-byte limit "
                    f"({self.max_document_xml_bytes})"
                )
            with archive.open(document_info) as source:
                payload = source.read(self.max_document_xml_bytes + 1)
            if len(payload) > self.max_document_xml_bytes:
                raise _DOCXValidationError(
                    "DOCX main document exceeds configured XML-byte limit "
                    f"({self.max_document_xml_bytes})"
                )
            return payload

    @staticmethod
    def _parse_document_xml(payload: bytes) -> tuple[ElementTree.Element, str]:
        upper = payload.upper()
        if b"<!DOCTYPE" in upper or b"<!ENTITY" in upper:
            raise _DOCXValidationError("DOCX XML declarations are not allowed")
        root = ElementTree.fromstring(payload)
        namespace = root.tag[1:].split("}", 1)[0] if root.tag.startswith("{") else ""
        if namespace not in _WORD_NAMESPACES or root.tag != f"{{{namespace}}}document":
            raise _DOCXValidationError("DOCX main part has an invalid root element")
        return root, f"{{{namespace}}}"

    def _extract_blocks(
        self, root: ElementTree.Element, word_prefix: str
    ) -> tuple[list[ContentBlock], dict[str, int]]:
        body = root.find(f"{word_prefix}body")
        if body is None:
            raise _DOCXValidationError("DOCX main document has no body")

        blocks: list[ContentBlock] = []
        current_section = ""
        paragraph_count = heading_count = list_item_count = 0
        table_count = table_row_count = 0

        def append(block: ContentBlock) -> None:
            if len(blocks) >= self.max_blocks:
                raise _DOCXValidationError(
                    f"DOCX exceeds configured block limit ({self.max_blocks})"
                )
            blocks.append(block)

        for child in body:
            if child.tag == f"{word_prefix}p":
                text = self._paragraph_text(child, word_prefix)
                if not text:
                    continue
                style = self._paragraph_style(child, word_prefix)
                is_heading = style.lower().startswith("heading") or style.lower() in {
                    "title",
                    "subtitle",
                }
                is_list = (
                    child.find(f"{word_prefix}pPr/{word_prefix}numPr") is not None
                )
                if is_heading:
                    current_section = text
                    kind = "heading"
                    heading_count += 1
                elif is_list:
                    kind = "list_item"
                    list_item_count += 1
                else:
                    kind = "text"
                    paragraph_count += 1
                append(
                    ContentBlock(
                        text,
                        kind=kind,
                        section=current_section,
                        metadata={"style": style} if style else {},
                    )
                )
            elif child.tag == f"{word_prefix}tbl":
                table_index = table_count
                table_count += 1
                for row_index, row in enumerate(child.findall(f"{word_prefix}tr")):
                    cells = [
                        self._cell_text(cell, word_prefix)
                        for cell in row.findall(f"{word_prefix}tc")
                    ]
                    if not any(cells):
                        continue
                    append(
                        ContentBlock(
                            " | ".join(cell.replace("|", "\\|") for cell in cells),
                            kind="table",
                            section=current_section,
                            metadata={
                                "table_index": table_index,
                                "row_index": row_index,
                                "columns": len(cells),
                            },
                        )
                    )
                    table_row_count += 1

        return blocks, {
            "block_count": len(blocks),
            "paragraph_count": paragraph_count,
            "heading_count": heading_count,
            "list_item_count": list_item_count,
            "table_count": table_count,
            "table_row_count": table_row_count,
        }

    @staticmethod
    def _paragraph_text(paragraph: ElementTree.Element, word_prefix: str) -> str:
        parts: list[str] = []
        for element in paragraph.iter():
            if element.tag == f"{word_prefix}t" and element.text:
                parts.append(element.text)
            elif element.tag == f"{word_prefix}tab":
                parts.append("\t")
            elif element.tag in {f"{word_prefix}br", f"{word_prefix}cr"}:
                parts.append("\n")
        return normalize_text("".join(parts))

    @staticmethod
    def _paragraph_style(paragraph: ElementTree.Element, word_prefix: str) -> str:
        style = paragraph.find(f"{word_prefix}pPr/{word_prefix}pStyle")
        return style.get(f"{word_prefix}val", "") if style is not None else ""

    @classmethod
    def _cell_text(cls, cell: ElementTree.Element, word_prefix: str) -> str:
        paragraphs = [
            cls._paragraph_text(item, word_prefix)
            for item in cell.findall(f"{word_prefix}p")
        ]
        return " ".join(item for item in paragraphs if item)
