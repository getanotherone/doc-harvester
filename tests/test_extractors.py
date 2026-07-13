from extractors import extract_web_html_blocks


def test_strips_script_style():
    html = "<html><body><script>alert(1)</script><style>.x{}</style><p>Content</p></body></html>"
    blocks = extract_web_html_blocks(html)
    text = " ".join(blocks)
    assert "alert" not in text
    assert ".x{}" not in text
    assert "Content" in text


def test_strips_nav_footer():
    html = """<html><body>
        <nav>Navigation menu</nav>
        <p>Real content here</p>
        <footer>Footer stuff</footer>
    </body></html>"""
    blocks = extract_web_html_blocks(html)
    text = " ".join(blocks)
    assert "Navigation menu" not in text
    assert "Footer stuff" not in text
    assert "Real content here" in text


def test_strips_boilerplate_class():
    html = """<html><body>
        <div class="sidebar">Sidebar junk</div>
        <p>Main text</p>
    </body></html>"""
    blocks = extract_web_html_blocks(html)
    text = " ".join(blocks)
    assert "Sidebar junk" not in text
    assert "Main text" in text


def test_strips_commercial_class():
    html = """<html><body>
        <div class="buy-block">Buy now for 999 rub</div>
        <p>Technical specification</p>
    </body></html>"""
    blocks = extract_web_html_blocks(html)
    text = " ".join(blocks)
    assert "Buy now" not in text
    assert "Technical specification" in text


def test_strips_commercial_phrases():
    html = """<html><body>
        <p>Добавить в корзину</p>
        <p>Сечение 3x2.5 мм²</p>
    </body></html>"""
    blocks = extract_web_html_blocks(html)
    text = " ".join(blocks)
    assert "корзину" not in text
    assert "Сечение" in text


def test_strips_buttons():
    html = """<html><body>
        <button>Click me</button>
        <p>Important info</p>
    </body></html>"""
    blocks = extract_web_html_blocks(html)
    text = " ".join(blocks)
    assert "Click me" not in text
    assert "Important info" in text


def test_prefers_main_tag():
    html = """<html><body>
        <div><p>Body noise one</p><p>Body noise two</p><p>Body noise three</p></div>
        <main>
            <h1>Product Title</h1>
            <p>Specs paragraph one</p>
            <p>Specs paragraph two</p>
        </main>
    </body></html>"""
    blocks = extract_web_html_blocks(html)
    text = " ".join(blocks)
    assert "Product Title" in text
    assert "Specs paragraph" in text


def test_empty_html():
    blocks = extract_web_html_blocks("")
    assert isinstance(blocks, list)
    assert len(blocks) == 0
