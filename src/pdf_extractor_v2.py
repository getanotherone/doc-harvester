import gc
import json
import os
import time

import requests
from pdfminer.high_level import extract_pages
from pdfminer.layout import LTTextContainer

try:
    import psutil  # optional dependency
except ImportError:  # pragma: no cover
    psutil = None


# =============================
# Streaming download
# =============================

def download_pdf_streaming(url: str, local_path: str) -> None:
    os.makedirs(os.path.dirname(local_path), exist_ok=True)

    with requests.get(url, stream=True, timeout=180) as response:
        response.raise_for_status()
        with open(local_path, "wb") as file:
            for chunk in response.iter_content(chunk_size=16 * 1024 * 1024):
                if chunk:
                    file.write(chunk)


def download_pdf_from_yandex(download_url: str, local_path: str) -> None:
    """Backward-compatible alias used by scraper.py."""
    download_pdf_streaming(download_url, local_path)


# =============================
# Page-level extraction
# =============================

def extract_text_from_layout(layout) -> str:
    text_parts = []
    for element in layout:
        if isinstance(element, LTTextContainer):
            text_parts.append(element.get_text())
    return "".join(text_parts).strip()


def ocr_page(file_path: str, page_number: int) -> str:
    from pdf2image import convert_from_path
    import pytesseract

    images = convert_from_path(
        file_path,
        first_page=page_number,
        last_page=page_number,
    )

    if not images:
        return ""

    return pytesseract.image_to_string(images[0]).strip()


def write_unit_json(units_dir: str, page_number: int, data: dict) -> None:
    os.makedirs(units_dir, exist_ok=True)
    filename = os.path.join(units_dir, f"{page_number:05d}.json")

    with open(filename, "w", encoding="utf-8") as file:
        json.dump(data, file, ensure_ascii=False, indent=2)


def get_existing_units(units_dir: str):
    if not os.path.exists(units_dir):
        return set()
    return {f for f in os.listdir(units_dir) if f.endswith(".json")}


# =============================
# Main extraction function
# =============================

def extract_pdf_to_units(file_path: str, output_dir: str, batch_size: int = 25):
    units_dir = os.path.join(output_dir, "units")
    os.makedirs(units_dir, exist_ok=True)

    existing_units = get_existing_units(units_dir)

    total_pages = 0
    processed_pages = 0
    ocr_pages = 0
    failed_pages = 0

    start_time = time.time()

    for _ in extract_pages(file_path):
        total_pages += 1

    for page_number, layout in enumerate(extract_pages(file_path), start=1):
        unit_filename = f"{page_number:05d}.json"
        if unit_filename in existing_units:
            continue

        page_start = time.time()

        try:
            text = extract_text_from_layout(layout)
            ocr_used = False

            if len(text) < 400:
                text = ocr_page(file_path, page_number)
                ocr_used = True
                if text:
                    ocr_pages += 1

            data = {
                "document_id": os.path.basename(file_path),
                "unit_index": page_number,
                "page_number": page_number,
                "char_count": len(text),
                "ocr_used": ocr_used,
                "processing_time_ms": int((time.time() - page_start) * 1000),
                "text": text,
            }

            write_unit_json(units_dir, page_number, data)
            processed_pages += 1

        except Exception as error:
            failed_pages += 1
            write_unit_json(
                units_dir,
                page_number,
                {
                    "document_id": os.path.basename(file_path),
                    "unit_index": page_number,
                    "page_number": page_number,
                    "error": str(error),
                    "text": "",
                },
            )

        if page_number % batch_size == 0:
            gc.collect()
            percent = (page_number / total_pages) * 100 if total_pages else 0
            if psutil:
                mem = psutil.Process(os.getpid()).memory_info().rss / (1024 * 1024)
                print(
                    f"[{os.path.basename(file_path)}] "
                    f"{page_number}/{total_pages} "
                    f"({percent:.1f}%) | RAM {mem:.0f} MB"
                )
            else:
                print(
                    f"[{os.path.basename(file_path)}] "
                    f"{page_number}/{total_pages} ({percent:.1f}%)"
                )

    total_time = int(time.time() - start_time)

    log = {
        "total_pages": total_pages,
        "processed_pages": processed_pages,
        "ocr_pages": ocr_pages,
        "failed_pages": failed_pages,
        "total_time_sec": total_time,
    }

    with open(os.path.join(output_dir, "extraction_log.json"), "w", encoding="utf-8") as file:
        json.dump(log, file, indent=2)

    return log
