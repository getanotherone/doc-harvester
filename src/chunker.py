"""Standalone chunker for web-crawled content (units -> blocks -> chunks).

Canonical chunking logic lives in services/doc_proc/ (DocProc microservice).
This module mirrors DocProc's domain/ patterns and chunking improvements
for use by the web scraper (src/scraper.py) without DocProc dependencies.

Keep in sync with:
  - services/doc_proc/backend/src/doc_proc/domain/patterns.py
  - services/doc_proc/backend/src/doc_proc/domain/block_classifier.py
  - services/doc_proc/backend/src/doc_proc/domain/metadata.py
  - services/doc_proc/backend/src/doc_proc/chunking/strategies/structure_aware.py
"""
import json
import os
import re
from functools import lru_cache
from typing import Dict, List, Optional, Tuple

import tiktoken

encoder = tiktoken.get_encoding("cl100k_base")
JSON_INDENT = int(os.environ.get("CHUNK_JSON_INDENT", "0"))

NORMATIVE_PATTERN = re.compile(
    r"^\s*((\d+(\.\d+){0,4})|([A-Za-zА-Яа-я]\))|([IVXLCMivxlcm]+\.))\s+"
)
SECTION_PATTERN = re.compile(
    r"^\s*((Раздел|Section|Глава)\s+\d+|\d+(\.\d+)*\s+[A-Za-zА-Яа-я])"
)
NUMBERED_HEADING_PATTERN = re.compile(r"^\s*(\d+(?:\.\d+){0,4})\s+(.+)$")
CODE_LINE_PATTERN = re.compile(r"^[A-ZА-ЯЁ]{1,4}[-\s]?\d{2,6}([-/][A-ZА-ЯЁ0-9]+)?$")
NUMERIC_HEAVY_PATTERN = re.compile(r"^[\d\s.,xXхХ\-–+/%°\"']+$")
TABLE_HINT_WORDS = (
    "артикул",
    "внутренние размеры",
    "внешние размеры",
    "размер ниши",
    "количество в упаковке",
    "шт.",
    "мм",
    "d1",
    "d2",
    "b1",
    "b2",
)
STANDARD_ID_REGEX = re.compile(
    r"(?:ГОСТ(?:\s+Р)?|GOST(?:\s+R)?|СНиП|SNIP|IEC|ISO)"
    r"\s*\d[\d.\-/–— ]{0,25}\d"           # require digit after prefix + digit-heavy tail
    r"|\b(?:СП|ФЗ)\s+\d[\d.\-/–— ]{0,25}\d",  # СП/ФЗ need word boundary (avoid "способ", "спектр")
    re.IGNORECASE,
)
YEAR_REGEX = re.compile(r"\b(19\d{2}|20[0-3]\d)\b")
CID_PATTERN = re.compile(r"\(cid:\d+\)")
VENDOR_PATTERNS = {
    "ABB": ("abb",),
    "Schneider": ("schneider", "se ", "шнайдер"),
    "Legrand": ("legrand", "легран"),
    "IEK": ("iek", "иэк"),
    "EKF": ("ekf",),
    "Hager": ("hager",),
    "DKC": ("dkc", "дкс"),
}


@lru_cache(maxsize=50000)
def _count_tokens_cached(text: str) -> int:
    return len(encoder.encode(text))


def count_tokens(text: str) -> int:
    return _count_tokens_cached(text or "")


def normalize_text(text: str) -> str:
    text = text.replace("\r", "")
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = re.sub(r"[ \t]+", " ", text)
    return text.strip()


def split_into_paragraphs(text: str) -> List[str]:
    paragraphs = re.split(r"\n\s*\n", text)
    return [p.strip() for p in paragraphs if p.strip()]


def _is_table_like(text: str) -> bool:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if len(lines) < 2:
        return False

    pipe_lines = sum(1 for line in lines if "|" in line)
    tab_lines = sum(1 for line in lines if "\t" in line)
    col_space_lines = sum(1 for line in lines if re.search(r"\S\s{2,}\S", line))

    if pipe_lines >= 2 or tab_lines >= 2:
        return True
    if col_space_lines >= 3 and len(lines) >= 4:
        return True

    lowered = text.lower()
    generic_table_words = ["наименование", "ед.", "кол-во", "qty", "unit", "amount"]
    if any(word in lowered for word in generic_table_words) and col_space_lines >= 2:
        return True

    table_hint_hits = sum(1 for word in TABLE_HINT_WORDS if word in lowered)
    code_lines = sum(1 for line in lines if CODE_LINE_PATTERN.match(line))
    numeric_lines = sum(
        1
        for line in lines
        if any(ch.isdigit() for ch in line)
        and (NUMERIC_HEAVY_PATTERN.match(line) or len(line.split()) <= 3)
    )
    short_lines = sum(1 for line in lines if len(line) <= 18)

    if table_hint_hits >= 1 and (numeric_lines >= 3 or code_lines >= 2):
        return True
    if code_lines >= 3 and numeric_lines >= 3:
        return True
    if len(lines) >= 8 and short_lines / len(lines) >= 0.65 and (code_lines + numeric_lines) >= 5:
        return True

    return False


def _is_normative_block(text: str) -> bool:
    first_line = text.splitlines()[0].strip() if text.strip() else ""
    return bool(NORMATIVE_PATTERN.match(first_line))


def _extract_section_heading(paragraph: str) -> Optional[Tuple[str, int]]:
    first_line = paragraph.splitlines()[0].strip() if paragraph.strip() else ""
    if len(first_line) > 140:
        return None

    numbered = NUMBERED_HEADING_PATTERN.match(first_line)
    if numbered:
        section_num = numbered.group(1)
        section_title = numbered.group(2).strip()
        level = section_num.count(".") + 1
        if section_title:
            return f"{section_num} {section_title}", min(level, 5)

    if SECTION_PATTERN.match(first_line):
        return first_line, 1

    if first_line.isupper() and len(first_line) <= 80:
        return first_line, 1

    return None


def _classify_block(paragraph: str) -> List[str]:
    labels: List[str] = []
    if _is_table_like(paragraph):
        labels.append("table")
    if _is_normative_block(paragraph):
        labels.append("normative")
    if not labels:
        labels.append("normal")
    return labels


def _update_section_stack(
    section_stack: List[str], heading: str, level: int
) -> List[str]:
    if level <= 1:
        return [heading]

    new_stack = list(section_stack)
    while len(new_stack) < level - 1:
        new_stack.append("")
    new_stack = new_stack[: level - 1]
    new_stack.append(heading)
    return [item for item in new_stack if item]


def load_units(units_dir: str) -> List[Dict]:
    if not os.path.isdir(units_dir):
        raise FileNotFoundError(f"Units directory not found: {units_dir}")

    unit_files = sorted(
        [name for name in os.listdir(units_dir) if name.endswith(".json")]
    )

    units = []
    for filename in unit_files:
        path = os.path.join(units_dir, filename)
        with open(path, "r", encoding="utf-8") as file:
            data = json.load(file)
        units.append(data)

    return units


def build_blocks_from_units(units: List[Dict]) -> List[Dict]:
    blocks = []
    section_stack: List[str] = []

    for unit in units:
        text = normalize_text(unit.get("text", ""))
        if not text:
            continue

        page = (
            unit.get("page")
            or unit.get("page_number")
            or unit.get("unit_index")
            or 0
        )
        document = unit.get("document") or unit.get("document_id") or ""

        paragraphs = split_into_paragraphs(text)

        for paragraph in paragraphs:
            heading = _extract_section_heading(paragraph)
            if heading:
                heading_text, heading_level = heading
                section_stack = _update_section_stack(
                    section_stack=section_stack,
                    heading=heading_text,
                    level=heading_level,
                )

            section_path = list(section_stack)
            section = section_path[-1] if section_path else ""
            section_level = len(section_path)

            block_types = _classify_block(paragraph)
            blocks.append(
                {
                    "document": document,
                    "page": int(page),
                    "section": section,
                    "section_path": section_path,
                    "section_level": section_level,
                    "text": paragraph,
                    "block_types": block_types,
                    "token_count": count_tokens(paragraph),
                }
            )

    return blocks


def _split_long_text(text: str, max_tokens: int) -> List[str]:
    """Split text on word boundaries, with a token-window fallback for long words."""
    pieces: List[str] = []
    current: List[str] = []
    for word in text.split():
        if count_tokens(word) > max_tokens:
            if current:
                pieces.append(" ".join(current))
                current = []
            token_ids = encoder.encode(word)
            pieces.extend(
                encoder.decode(token_ids[index : index + max_tokens])
                for index in range(0, len(token_ids), max_tokens)
            )
            continue
        candidate = " ".join([*current, word])
        if current and count_tokens(candidate) > max_tokens:
            pieces.append(" ".join(current))
            current = [word]
        else:
            current.append(word)
    if current:
        pieces.append(" ".join(current))
    return [piece for piece in pieces if piece]


def _split_normal_block(
    block: Dict, max_tokens: int, overlap_sentences: int = 2
) -> List[Dict]:
    text = block["text"]
    if block["token_count"] <= max_tokens:
        return [block]

    sentences = [
        piece
        for sentence in re.split(r"(?<=[.!?])\s+", text)
        if sentence.strip()
        for piece in _split_long_text(sentence.strip(), max_tokens)
    ]
    chunks = []
    current: List[str] = []
    current_tokens = 0

    for sentence in sentences:
        sentence_tokens = count_tokens(sentence)
        projected_tokens = current_tokens + sentence_tokens + (1 if current else 0)

        if projected_tokens > max_tokens and current:
            piece_text = " ".join(current)
            chunks.append(
                {
                    **block,
                    "text": piece_text,
                    "token_count": count_tokens(piece_text),
                }
            )
            # Overlap: carry last N sentences into the next chunk
            overlap = current[-overlap_sentences:] if overlap_sentences else []
            while overlap and count_tokens(" ".join([*overlap, sentence])) > max_tokens:
                overlap.pop(0)
            current = overlap + [sentence]
            current_tokens = count_tokens(" ".join(current))
        else:
            current.append(sentence)
            current_tokens = projected_tokens if current_tokens else sentence_tokens

    if current:
        piece_text = " ".join(current)
        chunks.append(
            {
                **block,
                "text": piece_text,
                "token_count": count_tokens(piece_text),
            }
        )

    if not chunks:
        return [block]
    return chunks


def _is_cid_garbage(text: str) -> bool:
    """Detect pdfminer font-decoding garbage like (cid:123) sequences."""
    if len(text) < 50:
        return False
    matches = CID_PATTERN.findall(text)
    return len(matches) > 5 and len(matches) * 10 > len(text) * 0.15


def _split_long_row(row: str, max_tokens: int) -> List[str]:
    """Split a single oversized table row at pipe/space boundaries."""
    if count_tokens(row) <= max_tokens:
        return [row]

    # Prefer splitting at pipe boundaries
    if "|" in row:
        segments = row.split("|")
    else:
        segments = row.split(" ")

    parts: List[str] = []
    current: List[str] = []
    current_tokens = 0
    sep = "|" if "|" in row else " "

    for seg in segments:
        seg_tokens = count_tokens(seg) + 1  # +1 for separator
        if current_tokens + seg_tokens > max_tokens and current:
            parts.append(sep.join(current))
            current = [seg]
            current_tokens = seg_tokens
        else:
            current.append(seg)
            current_tokens += seg_tokens

    if current:
        parts.append(sep.join(current))

    return parts if parts else [row]


def _split_table_block(block: Dict, max_tokens: int) -> List[Dict]:
    """Split an oversized table block by rows, preserving the header.

    Accounts for ~1 token per newline separator between rows to avoid
    accumulation drift on tables with many short rows. Falls back to
    splitting individual oversized rows at pipe/space boundaries.
    """
    text = block["text"]
    rows = text.split("\n")
    if not rows:
        return [block]

    header = rows[0]
    header_tokens = count_tokens(header)

    # If header itself is oversized, split it into separate chunks
    if header_tokens > max_tokens:
        header_parts = _split_long_row(header, max_tokens)
        sub_chunks: List[Dict] = []
        for part in header_parts:
            sub_chunks.append(
                {
                    **block,
                    "text": part,
                    "token_count": count_tokens(part),
                    "table_split": True,
                    "oversized": False,
                }
            )
        # Process remaining rows without header repetition
        remaining_text = "\n".join(rows[1:])
        if remaining_text.strip():
            remaining_block = {**block, "text": remaining_text, "token_count": count_tokens(remaining_text)}
            sub_chunks.extend(_split_table_block(remaining_block, max_tokens))
        return sub_chunks

    sub_chunks = []
    current_rows: List[str] = [header]
    current_tokens = header_tokens

    for row in rows[1:]:
        row_tokens = count_tokens(row) + 1  # +1 for \n separator token

        # Single row exceeds budget: split the row itself
        if row_tokens > max_tokens:
            # Flush current accumulator first
            if len(current_rows) > 1:
                chunk_text = "\n".join(current_rows)
                sub_chunks.append(
                    {
                        **block,
                        "text": chunk_text,
                        "token_count": count_tokens(chunk_text),
                        "table_split": True,
                        "oversized": False,
                    }
                )
            # Split the oversized row
            for part in _split_long_row(row, max_tokens):
                sub_chunks.append(
                    {
                        **block,
                        "text": f"{header}\n{part}",
                        "token_count": count_tokens(f"{header}\n{part}"),
                        "table_split": True,
                        "oversized": False,
                    }
                )
            current_rows = [header]
            current_tokens = header_tokens
            continue

        if current_tokens + row_tokens > max_tokens and len(current_rows) > 1:
            chunk_text = "\n".join(current_rows)
            sub_chunks.append(
                {
                    **block,
                    "text": chunk_text,
                    "token_count": count_tokens(chunk_text),
                    "table_split": True,
                    "oversized": False,
                }
            )
            current_rows = [header]
            current_tokens = header_tokens

        current_rows.append(row)
        current_tokens += row_tokens

    if current_rows:
        chunk_text = "\n".join(current_rows)
        sub_chunks.append(
            {
                **block,
                "text": chunk_text,
                "token_count": count_tokens(chunk_text),
                "table_split": True,
                "oversized": False,
            }
        )

    return sub_chunks if sub_chunks else [block]


def _merge_small_chunks(
    chunks: List[Dict], min_tokens: int = 150, max_tokens: int = 1200
) -> List[Dict]:
    """Merge adjacent small chunks to reduce fragment pollution."""
    if not chunks:
        return chunks

    VERY_TINY = 80  # Merge even across sections

    # Forward pass: merge small prev into next
    merged: List[Dict] = [chunks[0]]
    for chunk in chunks[1:]:
        prev = merged[-1]
        same_section = chunk.get("section") == prev.get("section")
        prev_tokens = prev.get("token_count", 0)
        combined_tokens = prev_tokens + chunk.get("token_count", 0)

        if (
            (prev_tokens < min_tokens and same_section)
            or prev_tokens < VERY_TINY
        ) and combined_tokens <= max_tokens:
            prev["text"] = f"{prev['text']}\n\n{chunk['text']}"
            prev["token_count"] = count_tokens(prev["text"])
            prev["end_page"] = max(prev.get("end_page", 0), chunk.get("end_page", 0))
            # Merge block_types
            prev["block_types"] = sorted(
                list(set(prev.get("block_types", []) + chunk.get("block_types", [])))
            )
            if not prev.get("section") and chunk.get("section"):
                prev["section"] = chunk["section"]
                prev["section_path"] = chunk.get("section_path", [])
                prev["section_level"] = chunk.get("section_level", 0)
        else:
            merged.append(chunk)

    # Backward pass: merge trailing small chunk into previous
    if len(merged) >= 2:
        last = merged[-1]
        prev = merged[-2]
        same_section = last.get("section") == prev.get("section")
        last_tokens = last.get("token_count", 0)
        combined_tokens = prev.get("token_count", 0) + last_tokens

        if (
            (last_tokens < min_tokens and same_section)
            or last_tokens < VERY_TINY
        ) and combined_tokens <= max_tokens:
            prev["text"] = f"{prev['text']}\n\n{last['text']}"
            prev["token_count"] = count_tokens(prev["text"])
            prev["end_page"] = max(prev.get("end_page", 0), last.get("end_page", 0))
            prev["block_types"] = sorted(
                list(set(prev.get("block_types", []) + last.get("block_types", [])))
            )
            merged.pop()

    return merged


def chunk_blocks_v2(
    blocks: List[Dict],
    target_tokens: int = 1000,
    max_tokens: int = 1200,
) -> Dict[str, List[Dict]]:
    chunks = []
    current_blocks: List[Dict] = []
    current_tokens = 0

    oversized_chunks = 0
    cid_garbage_blocks = 0
    table_split_chunks = 0
    protected_table_blocks = 0
    protected_normative_blocks = 0
    protected_table_normative_blocks = 0
    sectioned_blocks = 0

    def flush_current() -> None:
        nonlocal current_blocks, current_tokens
        if not current_blocks:
            return

        text = "\n\n".join(item["text"] for item in current_blocks).strip()
        start_page = min(item["page"] for item in current_blocks)
        end_page = max(item["page"] for item in current_blocks)

        section = ""
        section_path: List[str] = []
        section_level = 0
        for item in current_blocks:
            if item.get("section"):
                section = item["section"]
                section_path = item.get("section_path", [])
                section_level = item.get("section_level", 0)
                break

        chunk = {
            "document": current_blocks[0].get("document", ""),
            "page": start_page,
            "section": section,
            "section_path": section_path,
            "section_level": section_level,
            "chunk_index": len(chunks),
            "text": text,
            "token_count": count_tokens(text),
            "start_page": start_page,
            "end_page": end_page,
            "oversized": False,
            "block_types": sorted(
                list({label for item in current_blocks for label in item["block_types"]})
            ),
        }
        chunks.append(chunk)
        current_blocks = []
        current_tokens = 0

    for raw_block in blocks:
        if _is_cid_garbage(raw_block["text"]):
            cid_garbage_blocks += 1
            continue

        block_types = raw_block["block_types"]
        processed_blocks = [raw_block]

        if raw_block.get("section"):
            sectioned_blocks += 1

        if raw_block["token_count"] > max_tokens and "table" not in block_types:
            processed_blocks = _split_normal_block(raw_block, max_tokens=max_tokens)

        for block in processed_blocks:
            block_tokens = block["token_count"]
            protected = ("table" in block["block_types"]) or (
                "normative" in block["block_types"]
            )

            if "table" in block["block_types"]:
                protected_table_blocks += 1
            if "normative" in block["block_types"]:
                protected_normative_blocks += 1
            if ("table" in block["block_types"]) and (
                "normative" in block["block_types"]
            ):
                protected_table_normative_blocks += 1

            if protected and current_blocks and current_tokens + block_tokens > target_tokens:
                flush_current()

            if block_tokens > max_tokens:
                if current_blocks:
                    flush_current()
                if "table" in block["block_types"]:
                    sub_chunks = _split_table_block(block, max_tokens)
                    for sc in sub_chunks:
                        sc["chunk_index"] = len(chunks)
                        sc["start_page"] = block["page"]
                        sc["end_page"] = block["page"]
                        sc["block_types"] = block["block_types"]
                        chunks.append(sc)
                        table_split_chunks += 1
                else:
                    chunks.append(
                        {
                            "document": block.get("document", ""),
                            "page": block["page"],
                            "section": block.get("section", ""),
                            "section_path": block.get("section_path", []),
                            "section_level": block.get("section_level", 0),
                            "chunk_index": len(chunks),
                            "text": block["text"],
                            "token_count": block_tokens,
                            "start_page": block["page"],
                            "end_page": block["page"],
                            "oversized": True,
                            "block_types": block["block_types"],
                        }
                    )
                    oversized_chunks += 1
                continue

            if current_tokens + block_tokens > target_tokens and current_blocks:
                flush_current()

            current_blocks.append(block)
            current_tokens += block_tokens

    flush_current()

    # Merge small adjacent chunks to avoid fragment pollution
    chunks = _merge_small_chunks(chunks, min_tokens=150, max_tokens=max_tokens)

    # Reindex after merge
    for idx, chunk in enumerate(chunks):
        chunk["chunk_index"] = idx

    token_limit_violations = sum(
        1 for chunk in chunks if chunk.get("token_count", 0) > max_tokens and not chunk.get("oversized")
    )

    return {
        "chunks": chunks,
        "stats": {
            "total_blocks": len(blocks),
            "sectioned_blocks": sectioned_blocks,
            "protected_table_blocks": protected_table_blocks,
            "protected_normative_blocks": protected_normative_blocks,
            "protected_table_normative_blocks": protected_table_normative_blocks,
            "cid_garbage_blocks": cid_garbage_blocks,
            "table_split_chunks": table_split_chunks,
            "oversized_chunks": oversized_chunks,
            "token_limit_violations": token_limit_violations,
            "protected_split_violations": 0,
        },
    }


def write_chunks(chunks_dir: str, chunks: List[Dict]) -> None:
    os.makedirs(chunks_dir, exist_ok=True)

    for idx, chunk in enumerate(chunks):
        out_path = os.path.join(chunks_dir, f"{idx:05d}.json")
        with open(out_path, "w", encoding="utf-8") as file:
            if JSON_INDENT > 0:
                json.dump(chunk, file, ensure_ascii=False, indent=JSON_INDENT)
            else:
                json.dump(chunk, file, ensure_ascii=False, separators=(",", ":"))


def write_minimal_chunks(minimal_chunks_dir: str, chunks: List[Dict]) -> None:
    os.makedirs(minimal_chunks_dir, exist_ok=True)

    for idx, chunk in enumerate(chunks):
        metadata = _infer_stage3_metadata(chunk)
        minimal = {
            "document": chunk.get("document", ""),
            "page": chunk.get("page", 0),
            "section": chunk.get("section", ""),
            "chunk_index": chunk.get("chunk_index", idx),
            "text": chunk.get("text", ""),
            "doc_type": metadata["doc_type"],
            "vendor": metadata["vendor"],
            "standard_id": metadata["standard_id"],
            "year": metadata["year"],
            "lang": metadata["lang"],
            "source_type": metadata["source_type"],
            "quality_status": chunk.get("quality_status", "unknown"),
        }
        out_path = os.path.join(minimal_chunks_dir, f"{idx:05d}.json")
        with open(out_path, "w", encoding="utf-8") as file:
            if JSON_INDENT > 0:
                json.dump(minimal, file, ensure_ascii=False, indent=JSON_INDENT)
            else:
                json.dump(minimal, file, ensure_ascii=False, separators=(",", ":"))


def chunk_units_v2(
    units_dir: str,
    chunks_dir: str,
    target_tokens: int = 1000,
    max_tokens: int = 1200,
    minimal_chunks_dir: Optional[str] = None,
) -> Dict:
    units = load_units(units_dir)
    blocks = build_blocks_from_units(units)
    result = chunk_blocks_v2(blocks, target_tokens=target_tokens, max_tokens=max_tokens)

    chunks = result["chunks"]
    stats = result["stats"]

    write_chunks(chunks_dir, chunks)

    if minimal_chunks_dir:
        write_minimal_chunks(minimal_chunks_dir, chunks)

    token_counts = [chunk["token_count"] for chunk in chunks]

    log = {
        "total_units": len(units),
        "total_blocks": stats["total_blocks"],
        "sectioned_blocks": stats["sectioned_blocks"],
        "total_chunks": len(chunks),
        "target_tokens": target_tokens,
        "max_tokens": max_tokens,
        "avg_chunk_tokens": int(sum(token_counts) / len(token_counts)) if token_counts else 0,
        "max_chunk_tokens": max(token_counts) if token_counts else 0,
        "protected_table_blocks": stats["protected_table_blocks"],
        "protected_normative_blocks": stats["protected_normative_blocks"],
        "protected_table_normative_blocks": stats["protected_table_normative_blocks"],
        "cid_garbage_blocks": stats["cid_garbage_blocks"],
        "table_split_chunks": stats["table_split_chunks"],
        "oversized_chunks": stats["oversized_chunks"],
        "token_limit_violations": stats["token_limit_violations"],
        "protected_split_violations": stats["protected_split_violations"],
        "minimal_chunks_written": len(chunks) if minimal_chunks_dir else 0,
    }

    chunking_log_path = os.path.join(os.path.dirname(chunks_dir), "chunking_log.json")
    with open(chunking_log_path, "w", encoding="utf-8") as file:
        if JSON_INDENT > 0:
            json.dump(log, file, ensure_ascii=False, indent=JSON_INDENT)
        else:
            json.dump(log, file, ensure_ascii=False, separators=(",", ":"))

    return log


def _infer_stage3_metadata(chunk: Dict) -> Dict[str, object]:
    document = str(chunk.get("document", "") or "")
    section = str(chunk.get("section", "") or "")
    text = str(chunk.get("text", "") or "")
    probe_text = f"{document}\n{section}\n{text[:2000]}"
    lowered = probe_text.lower()

    source_type = "unknown"
    doc_base = os.path.basename(document)
    _, ext = os.path.splitext(doc_base.lower())
    if ext in {".pdf", ".docx", ".xlsx", ".html", ".htm", ".xml"}:
        source_type = ext.lstrip(".")

    vendor = ""
    for candidate, aliases in VENDOR_PATTERNS.items():
        if any(alias in lowered for alias in aliases):
            vendor = candidate
            break

    standard_id = ""
    standard_match = STANDARD_ID_REGEX.search(probe_text)
    if standard_match:
        standard_id = re.sub(r"\s+", " ", standard_match.group(0)).strip(" .,:;")

    year = None
    year_source = standard_id if standard_id else probe_text
    year_match = YEAR_REGEX.search(year_source)
    if year_match:
        year = int(year_match.group(1))

    cyrillic_count = sum(1 for ch in probe_text if "а" <= ch.lower() <= "я" or ch.lower() == "ё")
    latin_count = sum(1 for ch in probe_text if "a" <= ch.lower() <= "z")
    if cyrillic_count and latin_count:
        lang = "mixed"
    elif cyrillic_count:
        lang = "ru"
    elif latin_count:
        lang = "en"
    else:
        lang = "unknown"

    fire_tokens = ("пожар", "огнестой", "пожарн", "fire", "flame")
    normative_tokens = ("гост", "сп ", "снип", "пуэ", "пэу", "норматив", "стандарт", "regulation")
    catalog_tokens = ("каталог", "catalog", "datasheet", "технический каталог")
    if any(token in lowered for token in fire_tokens):
        doc_type = "fire"
    elif standard_id or any(token in lowered for token in normative_tokens):
        doc_type = "normative"
    elif vendor or any(token in lowered for token in catalog_tokens):
        doc_type = "catalog"
    else:
        doc_type = "technical"

    return {
        "doc_type": doc_type,
        "vendor": vendor,
        "standard_id": standard_id,
        "year": year,
        "lang": lang,
        "source_type": source_type,
    }


# Backward compatibility for legacy text-based callers.
def chunk_text_hybrid(text: str, target_tokens: int = 1000, overlap_tokens: int = 200):
    _ = overlap_tokens
    normalized = normalize_text(text)
    blocks = [
        {
            "document": "",
            "page": 0,
            "section": "",
            "section_path": [],
            "section_level": 0,
            "text": paragraph,
            "block_types": _classify_block(paragraph),
            "token_count": count_tokens(paragraph),
        }
        for paragraph in split_into_paragraphs(normalized)
    ]

    result = chunk_blocks_v2(
        blocks, target_tokens=target_tokens, max_tokens=target_tokens + 200
    )

    return [
        {
            "chunk_index": chunk["chunk_index"],
            "text": chunk["text"],
            "token_count": chunk["token_count"],
        }
        for chunk in result["chunks"]
    ]
