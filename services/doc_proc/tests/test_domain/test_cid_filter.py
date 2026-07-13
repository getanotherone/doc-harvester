"""Tests for CID garbage detection."""

from doc_proc.domain.cid_filter import is_cid_garbage


def test_clean_text_not_garbage():
    assert not is_cid_garbage("Кабель ВВГнг 3×2.5 ГОСТ 31996-2012")


def test_short_text_never_garbage():
    assert not is_cid_garbage("(cid:1)(cid:2)")


def test_cid_heavy_text_is_garbage():
    cid_text = " ".join(f"(cid:{i})" for i in range(20))
    assert is_cid_garbage(cid_text)


def test_mixed_text_with_few_cids_not_garbage():
    text = "Нормальный текст документа " * 20 + "(cid:1) (cid:2) (cid:3)"
    assert not is_cid_garbage(text)


def test_threshold_boundary():
    # Exactly 6 CIDs in short text — should be garbage
    cid_part = "(cid:10) " * 6
    text = "x" * 30 + cid_part
    assert is_cid_garbage(text)
