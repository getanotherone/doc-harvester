from __future__ import annotations

import json
import threading
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from doc_harvester.cli import main
from doc_harvester.manifest_processing import load_manifest


class LocalSiteHandler(BaseHTTPRequestHandler):
    requests: list[str] = []
    routes = {
        "/robots.txt": (
            200,
            "text/plain",
            b"User-agent: *\nDisallow: /private\n",
        ),
        "/": (
            200,
            "text/html",
            b'<a href="/guide">Guide</a><a href="/manual.pdf">Manual</a>'
            b'<a href="/private/secret">Private</a>',
        ),
        "/guide": (200, "text/html", b"<h1>Local guide</h1>"),
        "/manual.pdf": (200, "application/pdf", b"not fetched by crawler"),
        "/private/secret": (200, "text/html", b"must not be fetched"),
    }

    def do_GET(self):
        type(self).requests.append(self.path)
        status, media_type, body = self.routes.get(
            self.path, (404, "text/plain", b"not found")
        )
        self.send_response(status)
        self.send_header("Content-Type", media_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format, *args):
        del format, args


@contextmanager
def local_site():
    LocalSiteHandler.requests = []
    server = ThreadingHTTPServer(("127.0.0.1", 0), LocalSiteHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def test_source_crawl_builds_process_compatible_manifest_from_local_site(tmp_path):
    output = tmp_path / "crawl-manifest.json"
    with local_site() as origin:
        result = main(
            [
                "source",
                "crawl",
                f"{origin}/",
                "--delay",
                "0",
                "--limit",
                "10",
                "--output",
                str(output),
            ]
        )

    assert result == 0
    manifest = json.loads(output.read_text(encoding="utf-8"))
    assert manifest["schema_version"] == 1
    assert manifest["provider"] == "html"
    assert [resource["uri"] for resource in manifest["resources"]] == [
        f"{origin}/",
        f"{origin}/manual.pdf",
        f"{origin}/guide",
    ]
    assert manifest["crawl"]["skipped_robots"] == 1
    assert manifest["crawl"]["failed_fetches"] == 0
    assert load_manifest(output)["count"] == 3
    assert LocalSiteHandler.requests == ["/robots.txt", "/", "/guide"]
