import glob
import hashlib
import json
import os
import re
from datetime import datetime, timezone
from typing import Dict, List, Tuple

DEFAULT_MIN_TOKENS = int(os.environ.get("QUALITY_MIN_TOKENS", "40"))
DEFAULT_MAX_EMPTY_RATIO = float(os.environ.get("QUALITY_MAX_EMPTY_RATIO", "0.01"))
DEFAULT_MAX_TINY_RATIO = float(os.environ.get("QUALITY_MAX_TINY_RATIO", "0.35"))
DEFAULT_MAX_DUPLICATE_RATIO = float(os.environ.get("QUALITY_MAX_DUPLICATE_RATIO", "0.25"))
DEFAULT_MAX_NOISY_RATIO = float(os.environ.get("QUALITY_MAX_NOISY_RATIO", "0.30"))

TOKEN_RE = re.compile(r"[A-Za-zА-Яа-яЁё0-9]{3,}")
STOPWORDS = {
    "для", "при", "как", "что", "или", "это", "его", "еще", "ещё", "можно", "нужно",
    "когда", "какой", "какая", "какие", "где", "есть", "быть", "если", "ли", "по",
    "из", "на", "все", "всё", "the", "and", "for", "with", "from",
}


def _load_json(path: str) -> Dict:
    with open(path, "r", encoding="utf-8") as file:
        return json.load(file)


def _write_json(path: str, payload: Dict) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as file:
        json.dump(payload, file, ensure_ascii=False, indent=2)


def _safe_ratio(num: int, den: int) -> float:
    return float(num) / float(den) if den else 0.0


def _normalize_text(text: str) -> str:
    text = (text or "").replace("\r", "")
    text = re.sub(r"\s+", " ", text).strip().lower()
    return text


def _is_noisy_text(text: str) -> bool:
    if len(text) < 200:
        return False
    # (cid:) artifacts are always noise
    cid_count = text.count("(cid:")
    if cid_count > 5:
        return True
    # Pipe-separated tables are valid data
    pipe_lines = sum(1 for line in text.split("\n") if "|" in line)
    if pipe_lines >= 2:
        return False
    alpha = sum(1 for ch in text if ch.isalpha())
    digits = sum(1 for ch in text if ch.isdigit())
    symbols = sum(1 for ch in text if not ch.isalnum() and not ch.isspace())
    total = max(1, len(text))
    alpha_ratio = alpha / total
    symbol_ratio = symbols / total
    digit_ratio = digits / total
    return alpha_ratio < 0.45 and (symbol_ratio > 0.18 or digit_ratio > 0.40)


def _propagate_quality_status(document_dir: str, status: str) -> None:
    targets = []
    targets.extend(sorted(glob.glob(os.path.join(document_dir, "chunks", "*.json"))))
    targets.extend(sorted(glob.glob(os.path.join(document_dir, "chunks_minimal", "*.json"))))

    for path in targets:
        try:
            payload = _load_json(path)
        except Exception:
            continue

        if payload.get("quality_status") == status:
            continue

        payload["quality_status"] = status
        _write_json(path, payload)


def evaluate_quality_for_document(
    document_dir: str,
    min_tokens: int = DEFAULT_MIN_TOKENS,
    max_empty_ratio: float = DEFAULT_MAX_EMPTY_RATIO,
    max_tiny_ratio: float = DEFAULT_MAX_TINY_RATIO,
    max_duplicate_ratio: float = DEFAULT_MAX_DUPLICATE_RATIO,
    max_noisy_ratio: float = DEFAULT_MAX_NOISY_RATIO,
    write_report: bool = True,
) -> Dict:
    chunks_dir = os.path.join(document_dir, "chunks")
    chunk_paths = sorted(glob.glob(os.path.join(chunks_dir, "*.json")))

    if not chunk_paths:
        report = {
            "document_dir": document_dir,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "status": "fail",
            "reason": "chunks_not_found",
            "metrics": {"total_chunks": 0},
            "thresholds": {},
            "checks": [],
        }
        if write_report:
            _write_json(os.path.join(document_dir, "quality_gate.json"), report)
        return report

    total_chunks = 0
    empty_chunks = 0
    tiny_chunks = 0
    noisy_chunks = 0
    duplicate_hashes = {}
    max_token_count = 0
    sum_token_count = 0

    for path in chunk_paths:
        chunk = _load_json(path)
        text = chunk.get("text", "")
        token_count = int(chunk.get("token_count", 0))

        total_chunks += 1
        max_token_count = max(max_token_count, token_count)
        sum_token_count += token_count

        if not text or not text.strip():
            empty_chunks += 1
            continue

        if token_count < min_tokens:
            tiny_chunks += 1

        normalized = _normalize_text(text)
        text_hash = hashlib.sha1(normalized.encode("utf-8")).hexdigest()
        duplicate_hashes[text_hash] = duplicate_hashes.get(text_hash, 0) + 1

        if _is_noisy_text(normalized):
            noisy_chunks += 1

    duplicate_chunks = sum(count - 1 for count in duplicate_hashes.values() if count > 1)
    avg_token_count = int(sum_token_count / total_chunks) if total_chunks else 0

    empty_ratio = _safe_ratio(empty_chunks, total_chunks)
    tiny_ratio = _safe_ratio(tiny_chunks, total_chunks)
    duplicate_ratio = _safe_ratio(duplicate_chunks, total_chunks)
    noisy_ratio = _safe_ratio(noisy_chunks, total_chunks)

    checks = [
        {"name": "empty_ratio", "value": round(empty_ratio, 4), "max": max_empty_ratio, "ok": empty_ratio <= max_empty_ratio},
        {"name": "tiny_ratio", "value": round(tiny_ratio, 4), "max": max_tiny_ratio, "ok": tiny_ratio <= max_tiny_ratio},
        {"name": "duplicate_ratio", "value": round(duplicate_ratio, 4), "max": max_duplicate_ratio, "ok": duplicate_ratio <= max_duplicate_ratio},
        {"name": "noisy_ratio", "value": round(noisy_ratio, 4), "max": max_noisy_ratio, "ok": noisy_ratio <= max_noisy_ratio},
    ]

    status = "pass" if all(item["ok"] for item in checks) else "warn"
    report = {
        "document_dir": document_dir,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "metrics": {
            "total_chunks": total_chunks,
            "empty_chunks": empty_chunks,
            "tiny_chunks": tiny_chunks,
            "duplicate_chunks": duplicate_chunks,
            "noisy_chunks": noisy_chunks,
            "avg_token_count": avg_token_count,
            "max_token_count": max_token_count,
        },
        "ratios": {
            "empty_ratio": round(empty_ratio, 4),
            "tiny_ratio": round(tiny_ratio, 4),
            "duplicate_ratio": round(duplicate_ratio, 4),
            "noisy_ratio": round(noisy_ratio, 4),
        },
        "thresholds": {
            "max_empty_ratio": max_empty_ratio,
            "max_tiny_ratio": max_tiny_ratio,
            "max_duplicate_ratio": max_duplicate_ratio,
            "max_noisy_ratio": max_noisy_ratio,
            "min_tokens": min_tokens,
        },
        "checks": checks,
    }

    if write_report:
        _write_json(os.path.join(document_dir, "quality_gate.json"), report)
        _propagate_quality_status(document_dir=document_dir, status=status)

    return report


def _iter_document_dirs(datasets_root: str) -> List[str]:
    paths = glob.glob(os.path.join(datasets_root, "**", "chunks"), recursive=True)
    return sorted({os.path.dirname(path) for path in paths})


def evaluate_quality_for_dataset(
    datasets_root: str,
    refresh: bool = False,
    limit: int = 0,
) -> Dict:
    document_dirs = _iter_document_dirs(datasets_root)
    processed: List[Dict] = []
    skipped: List[Dict] = []

    for doc_dir in document_dirs:
        quality_path = os.path.join(doc_dir, "quality_gate.json")
        if not refresh and os.path.exists(quality_path):
            skipped.append({"document_dir": doc_dir, "reason": "quality_gate_exists"})
            continue

        report = evaluate_quality_for_document(doc_dir, write_report=True)
        processed.append(report)
        if limit and len(processed) >= limit:
            break

    pass_count = sum(1 for item in processed if item.get("status") == "pass")
    warn_count = sum(1 for item in processed if item.get("status") == "warn")

    return {
        "datasets_root": datasets_root,
        "processed_count": len(processed),
        "skipped_count": len(skipped),
        "pass_count": pass_count,
        "warn_count": warn_count,
        "processed": processed,
        "skipped": skipped,
    }


def _tokenize(text: str) -> List[str]:
    tokens = [tok.lower() for tok in TOKEN_RE.findall(text or "")]
    return [tok for tok in tokens if tok not in STOPWORDS]


def _load_chunks_for_eval(datasets_root: str, max_chunks: int = 0) -> Tuple[List[Dict], Dict[str, List[int]]]:
    chunk_paths = sorted(glob.glob(os.path.join(datasets_root, "**", "chunks_minimal", "*.json"), recursive=True))
    if not chunk_paths:
        chunk_paths = sorted(glob.glob(os.path.join(datasets_root, "**", "chunks", "*.json"), recursive=True))

    chunks: List[Dict] = []
    inverted: Dict[str, List[int]] = {}

    for path in chunk_paths:
        chunk = _load_json(path)
        text = (chunk.get("text") or "").strip()
        if not text:
            continue
        tokens = set(_tokenize(text))
        if not tokens:
            continue

        chunk_id = len(chunks)
        payload = {
            "chunk_id": chunk_id,
            "document": chunk.get("document", ""),
            "page": chunk.get("page", 0),
            "section": chunk.get("section", ""),
            "text": text,
            "tokens": tokens,
        }
        chunks.append(payload)

        for token in tokens:
            inverted.setdefault(token, []).append(chunk_id)

        if max_chunks and len(chunks) >= max_chunks:
            break

    return chunks, inverted


def run_auto_eval(
    datasets_root: str,
    questions_path: str,
    top_k: int = 5,
    max_chunks: int = 0,
) -> Dict:
    questions_payload = _load_json(questions_path)
    questions = questions_payload.get("questions", [])

    chunks, inverted = _load_chunks_for_eval(datasets_root=datasets_root, max_chunks=max_chunks)

    question_results = []
    hit_count = 0

    for item in questions:
        question = item.get("question", "")
        expected_terms = [term.lower() for term in item.get("expected_terms", [])]
        query_terms = set(_tokenize(question) + [token for term in expected_terms for token in _tokenize(term)])

        candidate_ids = set()
        for term in query_terms:
            for chunk_id in inverted.get(term, []):
                candidate_ids.add(chunk_id)
        if not candidate_ids:
            candidate_ids = set(range(len(chunks)))

        ranked = []
        for chunk_id in candidate_ids:
            chunk = chunks[chunk_id]
            overlap = len(query_terms & chunk["tokens"])
            expected_hits = sum(1 for term in expected_terms if term in chunk["text"].lower())
            score = overlap + (expected_hits * 3)
            if score <= 0:
                continue
            ranked.append((score, expected_hits, chunk))

        ranked.sort(key=lambda x: (x[0], x[1], len(x[2]["text"])), reverse=True)
        top = ranked[:top_k]
        hit = any(expected_hits > 0 for _, expected_hits, _ in top)
        if hit:
            hit_count += 1

        top_results = [
            {
                "score": score,
                "expected_hits": expected_hits,
                "document": chunk["document"],
                "page": chunk["page"],
                "section": chunk["section"],
                "text_preview": chunk["text"][:240],
            }
            for score, expected_hits, chunk in top
        ]

        question_results.append(
            {
                "id": item.get("id", ""),
                "question": question,
                "expected_terms": expected_terms,
                "hit_at_k": hit,
                "top_k": top_results,
            }
        )

    total_questions = len(question_results)
    hit_rate = _safe_ratio(hit_count, total_questions)

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "datasets_root": datasets_root,
        "questions_path": questions_path,
        "top_k": top_k,
        "total_chunks_indexed": len(chunks),
        "total_questions": total_questions,
        "hit_count": hit_count,
        "hit_rate": round(hit_rate, 4),
        "results": question_results,
    }
