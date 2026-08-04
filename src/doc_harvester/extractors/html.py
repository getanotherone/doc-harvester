"""HTML and XML extractor adapter."""

from __future__ import annotations

import warnings
from urllib.parse import urlsplit

from bs4 import BeautifulSoup, XMLParsedAsHTMLWarning
from chunker import normalize_text, split_into_paragraphs

from doc_harvester.core import ContentBlock, ExtractedDocument, Extractor, FetchedArtifact


class HTMLExtractor(Extractor):
    """Extract cleaned content blocks from static HTML/XML markup."""

    name = "html-xml"
    _MEDIA_TYPES = {
        "application/xhtml+xml",
        "application/xml",
        "text/html",
        "text/xml",
    }
    _EXTENSIONS = (".html", ".htm", ".xml", ".xhtml")

    def supports(self, artifact: FetchedArtifact) -> bool:
        media_type = artifact.media_type.split(";", 1)[0].strip().lower()
        candidate = (artifact.filename or urlsplit(artifact.resource.uri).path).lower()
        return media_type in self._MEDIA_TYPES or candidate.endswith(self._EXTENSIONS)

    def extract(self, artifact: FetchedArtifact) -> ExtractedDocument:
        if not self.supports(artifact):
            raise ValueError(f"{self.name} extractor does not support this artifact")
        decoded = artifact.content.decode("utf-8-sig", errors="replace")
        blocks = tuple(ContentBlock(text, kind="markup") for text in self._extract_blocks(decoded))
        return ExtractedDocument(
            artifact.resource,
            blocks,
            metadata={
                "extractor": self.name,
                "filename": artifact.filename,
                "media_type": artifact.media_type,
            },
        )

    @staticmethod
    def _extract_blocks(markup: str) -> list[str]:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", XMLParsedAsHTMLWarning)
            soup = BeautifulSoup(markup, "html.parser")
        for tag in soup(
            ["script", "style", "noscript", "svg", "meta", "link", "nav", "header", "footer", "aside"]
        ):
            tag.decompose()

        content = soup.find("main") or soup.find("article") or soup.body or soup
        blocks: list[str] = []
        for element in content.find_all(
            ["h1", "h2", "h3", "h4", "h5", "h6", "p", "li", "table", "pre", "blockquote", "dl"]
        ):
            if element.name == "table":
                rows: list[str] = []
                for row in element.find_all("tr"):
                    cells = [
                        normalize_text(cell.get_text(" ", strip=True))
                        for cell in row.find_all(["th", "td"])
                    ]
                    cells = [cell for cell in cells if cell]
                    if cells:
                        rows.append(" | ".join(cells))
                text = "\n".join(rows)
            else:
                text = normalize_text(element.get_text(" ", strip=True))
            if text:
                blocks.append(text)

        if not blocks:
            fallback = normalize_text(content.get_text("\n", strip=True))
            blocks = split_into_paragraphs(fallback)
        return list(dict.fromkeys(blocks))
