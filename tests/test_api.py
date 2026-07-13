def test_health_no_auth(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert "version" in data
    assert "active_tasks" in data


def test_sources_no_auth(client):
    resp = client.get("/sources")
    assert resp.status_code == 403


def test_sources_wrong_key(client):
    resp = client.get("/sources", headers={"X-API-Key": "wrong-key"})
    assert resp.status_code == 401


def test_sources_with_key(client, api_headers):
    resp = client.get("/sources", headers=api_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert "sources" in data
    assert "total" in data


def test_clean_html(client, api_headers):
    html = "<html><body><nav>Menu</nav><p>Technical specs</p></body></html>"
    resp = client.post("/clean-html", json={"html": html}, headers=api_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert "Technical specs" in data["cleaned_html"]
    assert "Menu" not in data["cleaned_html"]


def test_clean_html_sizes(client, api_headers):
    html = "<html><body><nav>Big navigation menu</nav><footer>Footer</footer><p>Small</p></body></html>"
    resp = client.post("/clean-html", json={"html": html}, headers=api_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["original_size"] > data["cleaned_size"]
