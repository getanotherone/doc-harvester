"""Text and table splitting utilities with overlap support."""

from __future__ import annotations

from doc_proc.models import CHARS_PER_TOKEN


def split_text(
    text: str,
    *,
    max_tokens: int = 512,
    overlap_tokens: int = 50,
) -> list[str]:
    """Split text into chunks within token limits.

    Prefers splitting at paragraph boundaries (\\n), then whitespace.
    """
    max_chars = max_tokens * CHARS_PER_TOKEN
    overlap_chars = overlap_tokens * CHARS_PER_TOKEN

    if len(text) <= max_chars:
        return [text] if text.strip() else []

    parts: list[str] = []
    start = 0

    while start < len(text):
        end = min(start + max_chars, len(text))

        if end < len(text):
            # Find best split point — prefer \n within last 20%
            search_start = end - int(max_chars * 0.2)
            newline_pos = text.rfind("\n", search_start, end)
            if newline_pos > start:
                end = newline_pos + 1
            else:
                # Fall back to whitespace
                space_pos = text.rfind(" ", search_start, end)
                if space_pos > start:
                    end = space_pos + 1

        chunk = text[start:end].strip()
        if chunk:
            parts.append(chunk)

        # Advance with overlap
        next_start = end - overlap_chars
        if next_start <= start:
            next_start = end  # Ensure forward progress
        start = next_start

    return parts


def split_table_with_header(
    table_text: str,
    *,
    max_tokens: int = 1536,
) -> list[str]:
    """Split a table by rows, repeating the first row (header) in each chunk.

    Works for any row-based format (pipe-separated, tab-separated, space-aligned).
    """
    rows = table_text.split("\n")
    if not rows:
        return [table_text] if table_text.strip() else []

    header = rows[0]
    max_chars = max_tokens * CHARS_PER_TOKEN
    header_chars = len(header) + 1

    parts: list[str] = []
    current_rows: list[str] = [header]
    current_chars = header_chars

    for row in rows[1:]:
        row_chars = len(row) + 1
        if current_chars + row_chars > max_chars and len(current_rows) > 1:
            parts.append("\n".join(current_rows))
            current_rows = [header]
            current_chars = header_chars

        current_rows.append(row)
        current_chars += row_chars

    if len(current_rows) > 1:  # Only append if there are data rows beyond the header
        parts.append("\n".join(current_rows))

    return parts if parts else [table_text]


def split_table_markdown(
    table_text: str,
    *,
    max_tokens: int = 1536,
    header_lines: int = 2,
) -> list[str]:
    """Split a markdown table, repeating header in each chunk."""
    lines = table_text.split("\n")
    if len(lines) <= header_lines:
        return [table_text] if table_text.strip() else []

    header = "\n".join(lines[:header_lines])
    data_lines = lines[header_lines:]
    max_chars = max_tokens * CHARS_PER_TOKEN
    header_chars = len(header) + 1  # +1 for newline

    parts: list[str] = []
    current_lines: list[str] = []
    current_chars = header_chars

    for line in data_lines:
        line_chars = len(line) + 1
        if current_chars + line_chars > max_chars and current_lines:
            parts.append(header + "\n" + "\n".join(current_lines))
            current_lines = []
            current_chars = header_chars

        current_lines.append(line)
        current_chars += line_chars

    if current_lines:
        parts.append(header + "\n" + "\n".join(current_lines))

    return parts if parts else [table_text]
