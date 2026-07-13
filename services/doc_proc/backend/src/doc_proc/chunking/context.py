"""Breadcrumb / context header injection for chunks."""

from __future__ import annotations

from doc_proc.models import RawChunk, estimate_tokens


def build_breadcrumb(section: str, doc_title: str = "") -> str:
    """Build a breadcrumb string from section path and document title."""
    parts: list[str] = []
    if doc_title:
        parts.append(doc_title)
    if section:
        parts.append(section)
    return " > ".join(parts)


def inject_context_headers(
    chunks: list[RawChunk],
    *,
    doc_title: str = "",
    domain_context: str = "",
) -> list[RawChunk]:
    """Inject breadcrumb headers into chunk text for better embedding quality.

    The breadcrumb is prepended to the text, separated by two newlines.
    Original context_header (e.g. product name for table chunks) is preserved
    and appended to the breadcrumb.
    """
    for chunk in chunks:
        breadcrumb = build_breadcrumb(chunk.section, doc_title)

        if domain_context:
            breadcrumb = f"{domain_context} | {breadcrumb}" if breadcrumb else domain_context

        if chunk.context_header:
            breadcrumb = (
                f"{breadcrumb} | {chunk.context_header}"
                if breadcrumb
                else chunk.context_header
            )

        if breadcrumb:
            chunk.context_header = breadcrumb
            chunk.text = f"{breadcrumb}\n\n{chunk.text}"
            chunk.token_count = estimate_tokens(chunk.text)

    return chunks
