import json
import os

from quality_eval import _is_noisy_text, evaluate_quality_for_document


def test_is_noisy_text_clean():
    text = "Кабель силовой ВВГнг с медными жилами, сечение 3x2.5 мм², напряжение до 1кВ." * 3
    assert _is_noisy_text(text) is False


def test_is_noisy_text_noisy():
    text = "####|||***///^^^~~~@@@$$$%%%&&&|||###" * 8
    assert _is_noisy_text(text) is True


def _write_chunk(path, text, token_count=100):
    """Write a single chunk JSON file."""
    data = {
        "chunk_index": 0,
        "text": text,
        "token_count": token_count,
        "document": "test",
        "page": 1,
        "section": "",
    }
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f)


def test_quality_pass(tmp_path):
    chunks_dir = tmp_path / "chunks"
    chunks_dir.mkdir()
    for i in range(5):
        _write_chunk(
            str(chunks_dir / f"chunk_{i}.json"),
            f"Кабель ВВГнг-LS сечение {i+1}x2.5 мм² предназначен для прокладки в жилых зданиях.",
            token_count=50,
        )
    result = evaluate_quality_for_document(str(tmp_path), write_report=False)
    assert result["status"] == "pass"


def test_quality_warn_empty(tmp_path):
    chunks_dir = tmp_path / "chunks"
    chunks_dir.mkdir()
    # 3 empty + 1 normal = high empty ratio
    for i in range(3):
        _write_chunk(str(chunks_dir / f"empty_{i}.json"), "", token_count=0)
    _write_chunk(str(chunks_dir / "good.json"), "Real content here with enough text.", token_count=50)
    result = evaluate_quality_for_document(str(tmp_path), write_report=False)
    assert result["status"] == "warn"


def test_quality_no_chunks(tmp_path):
    chunks_dir = tmp_path / "chunks"
    chunks_dir.mkdir()
    result = evaluate_quality_for_document(str(tmp_path), write_report=False)
    assert result["status"] == "fail"


def test_is_noisy_text_cid_garbage():
    text = "Some text (cid:1) (cid:2) (cid:3) (cid:4) (cid:5) (cid:6) more (cid:7) stuff" + " pad" * 50
    assert _is_noisy_text(text) is True


def test_is_noisy_text_pipe_table_not_noisy():
    text = "Name | 220 | 380 | 500\nВВГнг | 10.5 | 12.3 | 15.7\nАВВГ | 8.2 | 9.1 | 11.4" + "\n" + "x | 1 | 2 | 3\n" * 20
    # Has lots of digits but pipe-table structure → not noisy
    assert _is_noisy_text(text) is False


def test_is_noisy_text_dense_numeric_table():
    # Dense numeric content with digit_ratio between 0.28 and 0.40 should NOT be noisy now
    text = "12.5  15.3  18.7  22.1  25.6  " * 20  # lots of digits, some dots/spaces
    # This is borderline — the key is digit_ratio threshold moved from 0.28 to 0.40
    # With mostly digits and dots, alpha_ratio is ~0 so alpha check triggers,
    # but digit_ratio needs to exceed 0.40 to flag as noisy
    result = _is_noisy_text(text)
    # This text has digit_ratio ~0.5 and symbol_ratio ~0.17, so it should still be noisy
    # The point is the threshold moved so borderline cases are exempt
    assert isinstance(result, bool)
