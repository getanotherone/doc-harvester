from scraper import (
    _is_file_link,
    _is_product_url,
    _is_same_domain,
    _normalize_http_url,
    electrical_score,
    get_domain_name,
)


def test_get_domain_name():
    assert get_domain_name("https://www.cable.ru/products/") == "cable.ru"
    assert get_domain_name("https://cable.ru/products/") == "cable.ru"
    assert get_domain_name("http://ekf-electro.ru") == "ekf-electro.ru"


def test_is_file_link_pdf():
    assert _is_file_link("https://example.ru/doc.pdf") is True
    assert _is_file_link("https://example.ru/doc.pdf?v=2") is True
    assert _is_file_link("https://example.ru/file.xlsx") is True
    assert _is_file_link("https://example.ru/file.docx") is True


def test_is_file_link_html_page():
    assert _is_file_link("https://example.ru/page.php") is False
    assert _is_file_link("https://example.ru/catalog/") is False
    assert _is_file_link("https://example.ru/page.aspx") is False


def test_normalize_url():
    result = _normalize_http_url("https://cable.ru/cable/", "kabel-vvg.php")
    assert result == "https://cable.ru/cable/kabel-vvg.php"

    result = _normalize_http_url("https://cable.ru/cable/", "/about/#section")
    assert result == "https://cable.ru/about/"
    assert "#" not in result


def test_is_same_domain():
    assert _is_same_domain("https://cable.ru/a", "https://cable.ru/b") is True
    assert _is_same_domain("https://www.cable.ru/a", "https://cable.ru/b") is True
    assert _is_same_domain("https://cable.ru/a", "https://google.com/b") is False


def test_is_product_url_valid():
    assert _is_product_url("https://cable.ru/cable/kabel-vvg.php") is True
    assert _is_product_url("https://ekf.ru/catalog/avtomaty/") is True


def test_is_product_url_cart():
    assert _is_product_url("https://cable.ru/cart/") is False
    assert _is_product_url("https://example.ru/delivery/") is False
    assert _is_product_url("https://example.ru/login/") is False
    assert _is_product_url("https://example.ru/contacts/") is False


def test_electrical_score():
    text = "Кабель ВВГнг силовой электрический провод автомат"
    score = electrical_score(text)
    assert score > 0

    text_irrelevant = "Fashion trends summer collection youtube video"
    score_bad = electrical_score(text_irrelevant)
    assert score_bad < score
