"""Offline demonstration pipeline used by the CLI and tests."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from chunker import _infer_stage3_metadata, chunk_text_hybrid
from extractors import extract_web_html_blocks

DEMO_HTML = """
<!doctype html>
<html lang="ru">
  <body>
    <nav>Каталог | Доставка | Контакты</nav>
    <main>
      <h1>Технический каталог электрооборудования</h1>
      <h2>Кабели силовые</h2>
      <p>Кабель ВВГнг-LS 3x2.5 мм2, номинальное напряжение 660 В.</p>
      <table>
        <tr><th>Марка</th><th>Сечение</th><th>Напряжение</th></tr>
        <tr><td>ВВГнг-LS</td><td>3x2.5 мм2</td><td>660 В</td></tr>
        <tr><td>АВВГнг-LS</td><td>4x16 мм2</td><td>1000 В</td></tr>
      </table>
      <h2>Требования к монтажу</h2>
      <p>1.1 Кабельные линии следует прокладывать с соблюдением требований ГОСТ 31565-2012.</p>
      <button>Добавить в корзину</button>
    </main>
  </body>
</html>
"""


def build_demo_result() -> dict[str, Any]:
    """Run HTML extraction, chunking, and metadata enrichment without network access."""
    blocks = extract_web_html_blocks(DEMO_HTML)
    chunks = chunk_text_hybrid("\n\n".join(blocks), target_tokens=160)

    enriched = []
    for chunk in chunks:
        record = {
            "document": "demo-electrical-catalog.html",
            "page": 1,
            "section": "demo",
            **chunk,
        }
        record.update(_infer_stage3_metadata(record))
        enriched.append(record)

    return {
        "schema_version": 1,
        "source_type": "html",
        "blocks_extracted": len(blocks),
        "chunks": enriched,
    }


def write_demo_result(output: Path) -> dict[str, Any]:
    """Run the demo and write deterministic UTF-8 JSON output."""
    result = build_demo_result()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return result
