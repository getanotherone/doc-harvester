"""Strategy registry — maps names to Chunker implementations with auto-select."""

from __future__ import annotations

import logging
from typing import Any

from doc_proc.chunking.strategies.hierarchical import HierarchicalChunker
from doc_proc.chunking.strategies.row_group import RowGroupChunker
from doc_proc.chunking.strategies.row_level import RowLevelChunker
from doc_proc.chunking.strategies.semantic import SemanticChunker
from doc_proc.chunking.strategies.structure_aware import StructureAwareChunker
from doc_proc.models import ParseResult

logger = logging.getLogger(__name__)

REGISTRY: dict[str, type] = {
    "hierarchical": HierarchicalChunker,
    "structure_aware": StructureAwareChunker,
    "row_level": RowLevelChunker,
    "row_group": RowGroupChunker,
    "semantic": SemanticChunker,
}

DESCRIPTIONS: dict[str, str] = {
    "hierarchical": "Section-aware grouping for tabular data (default for Excel/CSV)",
    "structure_aware": "Semantic grouping by headings for PDF/DOCX documents",
    "row_level": "One row = one chunk — best for structured data matching",
    "row_group": "Groups N rows per chunk with section boundary splits",
    "semantic": "Regex pattern splitting for construction documents (Smeta, КСР codes)",
}


def get_chunker(name: str) -> Any:
    """Get a chunker instance by strategy name."""
    cls = REGISTRY.get(name)
    if cls is None:
        available = ", ".join(REGISTRY.keys())
        raise ValueError(f"Unknown strategy '{name}'. Available: {available}")
    return cls()


def auto_select(parse_result: ParseResult) -> str:
    """Auto-select optimal chunking strategy based on document characteristics.

    Decision tree:
    - format_hint == "tabular" → hierarchical (section-aware grouping)
    - format_hint == "document" → structure_aware (heading-based grouping)
    - format_hint == "mixed" → structure_aware (handles both text and tables)
    - Small tabular docs (< 50 elements) → row_level
    """
    hint = parse_result.format_hint
    n_elements = len(parse_result.elements)

    if hint == "tabular":
        if n_elements < 50:
            logger.info("Auto-selected row_level (small tabular doc, %d elements)", n_elements)
            return "row_level"
        logger.info("Auto-selected hierarchical (tabular doc, %d elements)", n_elements)
        return "hierarchical"

    if hint in ("document", "mixed"):
        logger.info("Auto-selected structure_aware (%s doc, %d elements)", hint, n_elements)
        return "structure_aware"

    logger.info("Auto-selected hierarchical (fallback, %d elements)", n_elements)
    return "hierarchical"


def list_strategies() -> list[dict[str, str]]:
    """List all available strategies with descriptions."""
    return [
        {"name": name, "description": DESCRIPTIONS.get(name, "")}
        for name in REGISTRY
    ]
