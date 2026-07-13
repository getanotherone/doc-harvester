import json
import os
import re
from typing import Dict, Iterable, List, Optional

from bs4 import BeautifulSoup

from chunker import normalize_text, split_into_paragraphs


def _write_unit_json(units_dir: str, unit_index: int, data: Dict) -> None:
    os.makedirs(units_dir, exist_ok=True)
    out_path = os.path.join(units_dir, f"{unit_index:05d}.json")
    with open(out_path, "w", encoding="utf-8") as file:
        json.dump(data, file, ensure_ascii=False, indent=2)


def _write_extraction_log(output_dir: str, log: Dict) -> Dict:
    out_path = os.path.join(output_dir, "extraction_log.json")
    with open(out_path, "w", encoding="utf-8") as file:
        json.dump(log, file, ensure_ascii=False, indent=2)
    return log


def _lines_to_units(
    lines: Iterable[str],
    output_dir: str,
    document_id: str,
    section: str,
    lines_per_unit: int = 50,
) -> Dict:
    units_dir = os.path.join(output_dir, "units")
    os.makedirs(units_dir, exist_ok=True)

    clean_lines = [normalize_text(line) for line in lines if normalize_text(line)]

    unit_index = 0
    for start in range(0, len(clean_lines), lines_per_unit):
        chunk = clean_lines[start : start + lines_per_unit]
        if not chunk:
            continue
        text = "\n".join(chunk)
        _write_unit_json(
            units_dir,
            unit_index + 1,
            {
                "document": document_id,
                "page": unit_index + 1,
                "section": section,
                "chunk_index": unit_index,
                "text": text,
            },
        )
        unit_index += 1

    return _write_extraction_log(
        output_dir,
        {
            "total_pages": unit_index,
            "processed_pages": unit_index,
            "ocr_pages": 0,
            "failed_pages": 0,
            "total_units": unit_index,
            "extractor": section,
        },
    )


_BOILERPLATE_CLASS_ID = re.compile(
    r"cookie|breadcrumb|sidebar|menu|nav|banner|advert|social|share|popup|modal|overlay",
    re.IGNORECASE,
)

# Commercial/e-commerce blocks to strip (ordering, delivery, pricing chrome)
_COMMERCIAL_CLASS_ID = re.compile(
    r"right.?column|sticky.?col|manager.?contact|subscribe.?form|cart|basket"
    r"|order.?form|buy.?block|price.?block|delivery.?block|add.?to.?cart"
    r"|purchase|checkout|wishlist|compare.?block|callback|feedback.?form"
    r"|links.?right|promo.?banner|action.?button|cta"
    # Reviews, ratings, recommendations
    r"|review|rating|stars|отзыв|рейтинг|recommend|similar.?product"
    r"|recently.?viewed|also.?bought|related.?product|accessories",
    re.IGNORECASE,
)

# Commercial text phrases — blocks containing these are stripped after extraction
_COMMERCIAL_PHRASES = re.compile(
    r"пришлите заявку|добавить в корзину|купить сейчас|в корзину|оформить заказ"
    r"|рассчитать доставку|минимальная сумма заказа|самовывоз|конкурентный счет"
    r"|предложим лучшую цену|способ[ыь]? оплаты|гарантия\s*[-–—]\s*\d+"
    r"|ответ в течение|подберите товар с менеджером|отправить заявку"
    r"|закажите звонок|заказать обратный звонок"
    r"|от \d+ руб|от \d+ дн|add to cart|buy now"
    r"|доставим в[:\s]|транспортной компанией|курьером"
    r"|огромный выбор|качество по госту"
    r"|\d+ товар[ов]*$"
    r"|^гарантия$|^цена\b|^цены на\b|^скидк|^акци[яи]$"
    # Help-desk / manager boilerplate (EKF-style)
    r"|нужна помощь в выборе|помощь в выборе|наши менеджеры"
    r"|свяжитесь с нами|задать вопрос менеджеру|помочь вам по телефону"
    r"|обратный звонок|написать менеджеру|связаться с менеджером"
    # Phone number blocks (8-800, +7, etc.)
    r"|8[\s-]?800[\s-]?\d{3}[\s-]?\d{2}[\s-]?\d{2}"
    r"|\+7[\s-]?\(?\d{3}\)?[\s-]?\d{3}[\s-]?\d{2}[\s-]?\d{2}"
    # Email in commercial context
    r"|электронной почте\s+\S+@\S+"
    # ── Prices (ruble amounts, "base price", retail price) ──
    r"|\d[\d\s]+₽"                              # any ruble price: "2 977 ₽", "827,16 ₽"
    r"|рекомендованная розничная цена"
    r"|базовая цена\s*\d"                        # "Базовая цена 189 ₽"
    r"|купить данный товар .+ по цене"           # systeme-russia "buy for X rub" paragraph
    r"|по цене \d+ руб"
    r"|по привлекательной цене"
    # ── Reviews, ratings, star scores ──
    r"|\d[\d.]*\s+из\s+\d+\s+звезд"             # "5 из 5 звезд"
    r"|^recent reviews$|^customer reviews$"
    r"|отзыв[оы]"
    # ── Cart/shop UI (keaz.ru etc.) ──
    r"|^нет в наличии$|^узнать наличие$|^узнать статус заказа$"
    r"|сроки готовности товара указаны в .+ корзине"
    r"|^в упаковке:$|^доступно$|^упак\.$"
    r"|^по убыванию$|^по возрастанию$"
    r"|^сравнить$|^избранное$"
    r"|изображение является справочным"
    # ── Stock/warehouse (tdme.ru) ──
    r"|на главном складе"
    r"|групповая упаковка \d+ шт"
    # ── SEO boilerplate (petrovich.ru) ──
    r"|в ассортименте интернет-магазина"
    r"|оформить и оплатить заказ можно"
    r"|условия продажи, доставки и цены"
    r"|рекомендуем ознакомиться с описанием"
    # ── Cookie/privacy banners ──
    r"|мы используем cookie"
    r"|вы соглашаетесь .+ метрических программ"
    r"|на нашем сайте используются"
    r"|рекомендательные технологии"
    r"|файлов cookie"
    # ── Dealer/payment boilerplate (systeme-russia.com) ──
    r"|официальный дилер продукции"
    r"|товар с гарантией производителя"
    r"|^где забрать\?$|^как оплатить\?$"
    r"|правила оплаты банковской картой"
    r"|^б/н расчет"
    # ── Recommendations / cross-sell sections ──
    r"|^вы недавно смотрели$|^последние просмотренные"
    r"|^аналоги и похожие товары$|^с этим товаром покупают$"
    r"|^вам могут понадобиться$|^рекомендуем вам$"
    r"|^популярные товары в категории$"
    # ── gostinform.ru boilerplate ──
    r"|^справочник по гостам, снипам, остам"
    r"|скачать документ бесплатно"
    r"|не нашли на портале нужный вам документ"
    r"|разместите нашу кнопку на своем сайте"
    r"|^html-код:$"
    r"|gostinform\.ru",
    re.IGNORECASE,
)


def extract_web_html_blocks(html_text: str) -> List[str]:
    """Extract content blocks from web page HTML, stripping navigation and boilerplate."""
    soup = BeautifulSoup(html_text, "html.parser")

    # Remove scripts, styles, and other non-content tags
    for tag in soup(["script", "style", "noscript", "svg", "meta", "link"]):
        tag.decompose()

    # Remove navigation chrome
    for tag in soup.find_all(["nav", "header", "footer", "aside"]):
        tag.decompose()

    # Remove common boilerplate by class/id patterns
    for tag in soup.find_all(attrs={"class": _BOILERPLATE_CLASS_ID}):
        tag.decompose()
    for tag in soup.find_all(attrs={"id": _BOILERPLATE_CLASS_ID}):
        tag.decompose()

    # Remove commercial/e-commerce blocks by class/id patterns
    for tag in soup.find_all(attrs={"class": _COMMERCIAL_CLASS_ID}):
        tag.decompose()
    for tag in soup.find_all(attrs={"id": _COMMERCIAL_CLASS_ID}):
        tag.decompose()

    # Remove button elements (ordering CTAs)
    for tag in soup.find_all("button"):
        tag.decompose()

    # Prefer <main> or <article> content if present
    main_content = soup.find("main") or soup.find("article")
    if main_content:
        # Check if main content area has enough substance
        test_blocks = _extract_html_blocks_from_tag(main_content)
        if len(test_blocks) >= 3:
            return _filter_commercial_blocks(test_blocks)

    # Fall back to body extraction
    body = soup.body or soup
    return _filter_commercial_blocks(_extract_html_blocks_from_tag(body))


def _extract_html_blocks_from_tag(tag) -> List[str]:
    """Extract text blocks from a BeautifulSoup tag (shared logic for HTML extraction)."""
    blocks: List[str] = []

    for el in tag.find_all(["h1", "h2", "h3", "h4", "p", "li", "table", "dl", "pre"]):
        if el.name == "table":
            rows = []
            for tr in el.find_all("tr"):
                cells = [normalize_text(cell.get_text(" ", strip=True)) for cell in tr.find_all(["th", "td"])]
                cells = [cell for cell in cells if cell]
                if cells:
                    rows.append(" | ".join(cells))
            if rows:
                blocks.append("\n".join(rows))
            continue

        if el.name == "dl":
            items = []
            for child in el.children:
                if getattr(child, "name", None) in ("dt", "dd"):
                    text = normalize_text(child.get_text(" ", strip=True))
                    if text:
                        items.append(text)
            if items:
                blocks.append("\n".join(items))
            continue

        text = normalize_text(el.get_text(" ", strip=True))
        if text:
            blocks.append(text)

    if not blocks:
        fallback_text = normalize_text(tag.get_text("\n", strip=True))
        blocks = split_into_paragraphs(fallback_text)

    return blocks


# Review date lines like "июнь 2025 г.", "февр. 2025 г." — indicates a review block
_REVIEW_DATE_RE = re.compile(
    r"^(янв|февр|март|апр|май|июн|июл|авг|сент|окт|нояб|дек)\S*\s+\d{4}\s*г?\.\s*$",
    re.IGNORECASE,
)

# Blocks that are just a bare number (article IDs from "related products" sections)
_BARE_NUMBER_RE = re.compile(r"^\d{4,}$")


def _filter_commercial_blocks(blocks: List[str]) -> List[str]:
    """Remove commercial blocks and deduplicate repeated blocks within a page."""
    # Strip commercial phrases
    cleaned = [b for b in blocks if not _COMMERCIAL_PHRASES.search(b)]
    # Strip review dates ("июнь 2025 г."), bare article IDs ("618765")
    cleaned = [b for b in cleaned
               if not _REVIEW_DATE_RE.match(b.strip()) and not _BARE_NUMBER_RE.match(b.strip())]
    # Deduplicate: keep first occurrence of each block (fixes EKF-style repeated boilerplate)
    seen: set[str] = set()
    deduped: List[str] = []
    for block in cleaned:
        key = block.strip().lower()
        if key not in seen:
            seen.add(key)
            deduped.append(block)
    return deduped


def extract_html_string_to_units(
    html_text: str, output_dir: str, document_id: str, section: str = "web_html"
) -> Dict:
    """Extract units from an HTML string using the web-optimized extractor."""
    blocks = extract_web_html_blocks(html_text)
    return _lines_to_units(
        lines=blocks,
        output_dir=output_dir,
        document_id=document_id,
        section=section,
        lines_per_unit=30,
    )


# ── SPA extraction (for JS-rendered sites like petrovich.ru) ──

# Noise lines to strip from rendered text — navigation, UI chrome, short CTAs
_SPA_NOISE_PATTERNS = re.compile(
    r"^(каталог|корзина|избранное|войти|меню|заказы|сравнить|поделиться|ещё|назад"
    r"|магазины|распродажа|акции|новинки|показать ещё|загрузить ещё|читать далее"
    r"|нашли дешевле|в корзину|в избранное|в смету|сравнить|©|политика"
    r"|cookie|подписаться|рассылк|наверх|скачать приложение|закрыть"
    r"|стройматериалы|инструмент|финишная отделка|товары для дома|сантехника|крепеж"
    r"|сад и досуг|инженерные системы|найти|сервисы|сметы"
    r"|вакансии|о нас|о компании|новости|история компании"
    r"|пресс-служба|служба поддержки|подарочные|клуб друзей"
    r"|мы принимаем к оплате|мобильные приложения|отсканируйте"
    r"|биржа профессионалов|петрович b2b|возврат товара|для юридических лиц"
    r"|распил|колеровка|аренда инструмента|переборка|расчет материалов"
    r"|установка дверей|укладка|замер|приемка квартир|помощник по дизайну"
    r"|программы лояльности|b2b|зарегистрировать карту|каталог призов"
    r"|аналоги|популярно в категории|вам могут понадобиться"
    r"|сопутствующие предложения|доставка и подъем"
    r"|описание|детали|характеристики|отзывы|вопросы|сертификаты"
    r"|штуку|штука|цена за|код:|похожие"
    r"|на нашем сайте используются|рекомендательные технологии"
    r"|соглашаетесь на использование|файлов cookie)$",
    re.IGNORECASE,
)

# Price/delivery noise
_SPA_PRICE_PATTERN = re.compile(
    r"^\d[\d\s]*₽$|^от\s+\d|^\d+\s*(шт|руб|р\.|₽)|^доставк|^самовывоз"
    r"|^привезем|^наличие|^в наличии|^нет в наличии|^под заказ"
    r"|^долями|^плати частями|^рассрочк|^доставим"
    r"|^если мы опоздали|^при заказе|^круглосуточно"
    r"|^товар на складе|^\d+\s*шт$"
    r"|^делите стоимость|^сейчас\s+\d|^\d+/\d+\s+в\s+\d"
    r"|оставаясь на сайте",
    re.IGNORECASE,
)

# Footer/related products section markers — everything after these is noise
_SPA_FOOTER_MARKERS = re.compile(
    r"^(о компании|покупателям|контакты|© \d{4}|при полном или частичном)$",
    re.IGNORECASE,
)

# Related products / recommendations section headers
_SPA_RELATED_SECTION = re.compile(
    r"вам могут понадобиться|сопутствующие|похожие товары|с этим товаром|"
    r"рекомендуем также|популярно в категории|аналоги|покупают вместе|"
    r"вы смотрели|недавно просмотренные|вас может заинтересовать",
    re.IGNORECASE,
)

# SEO filler text at page bottom
_SPA_SEO_FILLER = re.compile(
    r"в ассортименте (интернет-)?магазина|оформить и оплатить заказ|"
    r"условия продажи|можно купить с доставкой|рекомендуем ознакомиться с описанием|"
    r"доступны по привлекательной цене",
    re.IGNORECASE,
)


def extract_spa_blocks(rendered_text: str) -> List[str]:
    """Extract structured content blocks from browser-rendered inner text.

    Works with the output of page.inner_text('body') — plain text with
    newline-separated content. Returns blocks in the same format as
    extract_web_html_blocks() for compatibility with the rest of the pipeline.

    Strategy:
    1. Split into lines and filter navigation/commercial noise
    2. Detect product title and breadcrumbs
    3. Detect spec tables (lines with : or | separators)
    4. Cut at footer markers (related products, company info)
    5. Group remaining text into coherent blocks
    """
    if not rendered_text or not rendered_text.strip():
        return []

    lines = rendered_text.split("\n")
    blocks: List[str] = []
    current_section: List[str] = []
    spec_table: List[str] = []
    found_product_title = False
    in_related = False

    def flush_section():
        if spec_table:
            blocks.append("\n".join(spec_table))
            spec_table.clear()
        if current_section:
            text = "\n".join(current_section)
            if len(text) > 20:  # skip tiny fragments
                blocks.append(text)
            current_section.clear()

    for raw_line in lines:
        line = raw_line.strip()

        # Skip empty or very short lines
        if not line or len(line) < 3:
            if current_section or spec_table:
                flush_section()
            continue

        # Footer detection — stop processing
        if found_product_title and _SPA_FOOTER_MARKERS.match(line):
            flush_section()
            break

        # Related products section — skip until next spec-table content
        # Only activate after we've accumulated some real content (avoids
        # sidebar widgets that appear before the main product description)
        if _SPA_RELATED_SECTION.search(line):
            flush_section()
            in_related = True
            continue

        # SEO filler
        if _SPA_SEO_FILLER.search(line):
            continue

        # Skip navigation and noise
        if _SPA_NOISE_PATTERNS.match(line):
            continue
        if _SPA_PRICE_PATTERN.match(line):
            continue
        if _COMMERCIAL_PHRASES.search(line):
            continue

        # Skip short lines that look like store names or navigation items
        if len(line) < 30 and line.startswith("—"):
            continue  # store locations like "— Петрович Рядом Войковская"

        # Track when we've found the actual product content
        if not found_product_title and len(line) > 40:
            found_product_title = True

        # Detect spec-table lines: "Ключ: Значение" or "Ключ | Значение"
        is_spec_line = (
            re.match(r"^[А-Яа-яA-Za-z\s,/()]{3,50}\s*[:|]\s*.+", line)
            and len(line) < 200
        )

        # If in related products section, skip short lines (product names, categories)
        # but re-enter on spec-table lines or long descriptive paragraphs
        if in_related:
            if is_spec_line or len(line) > 100:
                in_related = False  # found real content — re-enter
            else:
                continue

        if is_spec_line:
            if current_section:
                text = "\n".join(current_section)
                if len(text) > 20:
                    blocks.append(text)
                current_section.clear()
            # Normalize separator to pipe for consistency
            normalized = re.sub(r"\s*:\s*", " | ", line, count=1) if ":" in line else line
            spec_table.append(normalized)
        else:
            if spec_table:
                blocks.append("\n".join(spec_table))
                spec_table.clear()
            current_section.append(line)

    flush_section()

    # Apply same commercial filter + dedup as HTML extractor
    return _filter_commercial_blocks(blocks)


def extract_spa_to_units(
    rendered_text: str, output_dir: str, document_id: str, section: str = "web_spa"
) -> Dict:
    """Extract units from SPA-rendered text (page.inner_text output)."""
    blocks = extract_spa_blocks(rendered_text)
    return _lines_to_units(
        lines=blocks,
        output_dir=output_dir,
        document_id=document_id,
        section=section,
        lines_per_unit=30,
    )
