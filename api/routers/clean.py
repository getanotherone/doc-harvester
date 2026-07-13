import os
import sys
from pathlib import Path

from fastapi import APIRouter

from ..models import CleanHtmlRequest, CleanHtmlResponse

router = APIRouter()

PROJECT_ROOT = Path(__file__).parent.parent.parent


@router.post("/clean-html", response_model=CleanHtmlResponse)
def clean_html(request: CleanHtmlRequest):
    src_path = str(PROJECT_ROOT / "src")
    if src_path not in sys.path:
        sys.path.insert(0, src_path)

    os.environ.setdefault("YANDEX_DISK_TOKEN", "__api_mode__")

    from bs4 import BeautifulSoup

    from extractors import extract_web_html_blocks

    original_size = len(request.html.encode("utf-8"))

    soup_before = BeautifulSoup(request.html, "html.parser")
    elements_before = len(list(soup_before.find_all()))

    blocks = extract_web_html_blocks(request.html)
    cleaned_html = "\n\n".join(blocks)
    cleaned_size = len(cleaned_html.encode("utf-8"))

    # Approximate removed elements count
    soup_after = BeautifulSoup(cleaned_html, "html.parser")
    elements_after = len(list(soup_after.find_all()))
    removed_elements = max(0, elements_before - elements_after)

    return CleanHtmlResponse(
        cleaned_html=cleaned_html,
        removed_elements=removed_elements,
        original_size=original_size,
        cleaned_size=cleaned_size,
    )
