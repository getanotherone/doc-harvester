from chunker import (
    _infer_stage3_metadata,
    _is_cid_garbage,
    _is_normative_block,
    _is_table_like,
    _split_table_block,
    chunk_blocks_v2,
    count_tokens,
    normalize_text,
    split_into_paragraphs,
)


def test_normalize_text():
    assert normalize_text("  hello   world  ") == "hello world"
    assert normalize_text("line1\r\nline2") == "line1\nline2"


def test_normalize_text_collapses_newlines():
    text = "a\n\n\n\n\nb"
    result = normalize_text(text)
    assert "\n\n\n" not in result
    assert "a\n\nb" == result


def test_split_into_paragraphs():
    text = "First paragraph.\n\nSecond paragraph.\n\nThird."
    parts = split_into_paragraphs(text)
    assert len(parts) == 3
    assert parts[0] == "First paragraph."
    assert parts[2] == "Third."


def test_count_tokens():
    tokens = count_tokens("Hello world, this is a test.")
    assert isinstance(tokens, int)
    assert tokens > 0


def test_is_table_like_pipes():
    text = "Name | Value | Unit\nVoltage | 220 | V\nCurrent | 10 | A"
    assert _is_table_like(text) is True


def test_is_table_like_plain():
    text = "This is a regular paragraph with no table structure whatsoever."
    assert _is_table_like(text) is False


def test_is_normative_block():
    assert _is_normative_block("1.2.3 Requirements for installation") is True
    assert _is_normative_block("a) First sub-item of the list") is True
    assert _is_normative_block("Regular paragraph text") is False


def _make_block(text, page=1, document="test"):
    """Helper to create a block dict for chunk_blocks_v2."""
    from chunker import _classify_block

    return {
        "text": text,
        "token_count": count_tokens(text),
        "block_types": _classify_block(text),
        "page": page,
        "document": document,
        "section": "",
        "section_path": [],
        "section_level": 0,
    }


def test_chunk_blocks_basic():
    blocks = [_make_block(f"Paragraph number {i} with some content.") for i in range(5)]
    result = chunk_blocks_v2(blocks, target_tokens=50, max_tokens=100)
    assert "chunks" in result
    assert "stats" in result
    assert len(result["chunks"]) > 0
    chunk = result["chunks"][0]
    assert "text" in chunk
    assert "token_count" in chunk
    assert "chunk_index" in chunk


def test_chunk_blocks_token_limit():
    blocks = [_make_block(f"Paragraph {i}. " * 10) for i in range(10)]
    result = chunk_blocks_v2(blocks, target_tokens=100, max_tokens=200)
    assert all(chunk["token_count"] <= 200 for chunk in result["chunks"])
    assert all(chunk.get("oversized") is False for chunk in result["chunks"])


def test_chunk_blocks_splits_long_unpunctuated_and_normative_blocks():
    unpunctuated = _make_block("technical " * 200)
    normative = _make_block("1.1 " + ("requirement " * 200))
    long_lexical_token = _make_block("абвгд" * 500)

    result = chunk_blocks_v2(
        [unpunctuated, normative, long_lexical_token],
        target_tokens=40,
        max_tokens=50,
    )

    assert len(result["chunks"]) > 2
    assert all(chunk["token_count"] <= 50 for chunk in result["chunks"])
    assert result["stats"]["oversized_chunks"] == 0
    assert result["stats"]["token_limit_violations"] == 0


def test_chunk_blocks_table_protected():
    table_text = "Name | Value | Unit\nVoltage | 220 | V\nCurrent | 10 | A"
    blocks = [
        _make_block("Some intro text before the table."),
        _make_block(table_text),
        _make_block("Text after the table."),
    ]
    result = chunk_blocks_v2(blocks, target_tokens=50, max_tokens=500)
    # Table should appear intact in one chunk
    for chunk in result["chunks"]:
        if "Voltage" in chunk["text"]:
            assert "Current" in chunk["text"]
            break
    else:
        raise AssertionError("Table text not found in any chunk")


def test_infer_metadata_vendor():
    chunk = {"text": "Автоматический выключатель ABB S201 C16", "document": "test.pdf"}
    meta = _infer_stage3_metadata(chunk)
    assert meta["vendor"] == "ABB"


def test_infer_metadata_standard():
    chunk = {"text": "Согласно ГОСТ Р 50571.5.52-2011 требования к прокладке", "document": "test.pdf"}
    meta = _infer_stage3_metadata(chunk)
    assert "ГОСТ" in meta.get("standard_id", "")


# --- _is_cid_garbage tests ---

def test_cid_garbage_positive():
    text = "(cid:12) (cid:34) (cid:56) (cid:78) (cid:90) (cid:11) abc"
    assert _is_cid_garbage(text) is True


def test_cid_garbage_short_text():
    text = "(cid:1) (cid:2)"
    assert _is_cid_garbage(text) is False


def test_cid_garbage_few_cids():
    text = "Normal text with a single (cid:1) artifact in a long paragraph. " * 5
    assert _is_cid_garbage(text) is False


def test_cid_garbage_clean_text():
    text = "This is perfectly normal technical content about cables and wiring." * 3
    assert _is_cid_garbage(text) is False


# --- _split_table_block tests ---

def test_split_table_block_basic():
    rows = ["Header | Col1 | Col2"]
    for i in range(50):
        rows.append(f"Row{i} | val{i} | val{i}")
    text = "\n".join(rows)
    block = _make_block(text)
    block["block_types"] = ["table"]

    sub_chunks = _split_table_block(block, max_tokens=100)
    assert len(sub_chunks) > 1
    # Each sub-chunk should start with the header
    for sc in sub_chunks:
        assert sc["text"].startswith("Header | Col1 | Col2")
        assert sc.get("table_split") is True
        assert sc.get("oversized") is False


def test_split_table_block_small():
    text = "Header | A | B\nRow1 | 1 | 2\nRow2 | 3 | 4"
    block = _make_block(text)
    block["block_types"] = ["table"]

    sub_chunks = _split_table_block(block, max_tokens=5000)
    assert len(sub_chunks) == 1
    assert sub_chunks[0]["text"] == text


# --- chunk_blocks_v2 integration tests for new features ---

def test_chunk_blocks_cid_garbage_filtered():
    cid_text = "(cid:12) (cid:34) (cid:56) (cid:78) (cid:90) (cid:11) (cid:22) garbage"
    blocks = [
        _make_block("Normal text before."),
        _make_block(cid_text),
        _make_block("Normal text after."),
    ]
    result = chunk_blocks_v2(blocks, target_tokens=500, max_tokens=1000)
    stats = result["stats"]
    assert stats["cid_garbage_blocks"] == 1
    # CID garbage text should not appear in any chunk
    for chunk in result["chunks"]:
        assert "(cid:12)" not in chunk["text"]


def test_chunk_blocks_oversized_table_split():
    rows = ["Name | Value | Unit"]
    for i in range(100):
        rows.append(f"Item{i} | {i * 10} | mm")
    text = "\n".join(rows)
    block = {
        "text": text,
        "token_count": count_tokens(text),
        "block_types": ["table"],
        "page": 1,
        "document": "test",
        "section": "",
        "section_path": [],
        "section_level": 0,
    }
    result = chunk_blocks_v2([block], target_tokens=100, max_tokens=150)
    stats = result["stats"]
    assert stats["table_split_chunks"] > 1
    assert stats["oversized_chunks"] == 0
    # Each split chunk should have the header
    for chunk in result["chunks"]:
        assert chunk["text"].startswith("Name | Value | Unit")
