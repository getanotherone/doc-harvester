from __future__ import annotations

import json
import threading
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from doc_harvester.cli import main
from tests.docx_fixture import build_docx, paragraph, table
from tests.pdf_fixture import build_text_pdf
from tests.xlsx_fixture import build_xlsx


class GoldenPathSiteHandler(BaseHTTPRequestHandler):
    requests: list[str] = []
    routes: dict[str, tuple[int, str, bytes]] = {}

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


def _site_routes() -> dict[str, tuple[int, str, bytes]]:
    return {
        "/robots.txt": (
            200,
            "text/plain",
            b"User-agent: *\nDisallow: /private\n",
        ),
        "/": (
            200,
            "text/html",
            b"<main><h1>Equipment library</h1><p>Reviewed technical samples.</p>"
            b'<a href="/guide.html">Guide</a>'
            b'<a href="/manual.pdf">PDF</a>'
            b'<a href="/catalog.docx">DOCX</a>'
            b'<a href="/inventory.xlsx">XLSX</a>'
            b'<a href="/feed.xml">XML</a>'
            b'<a href="/notes.txt">Text</a>'
            b'<a href="/private/secret">Private</a></main>',
        ),
        "/guide.html": (
            200,
            "text/html",
            b"<main><h1>Installation guide</h1>"
            b"<p>Disconnect power, mount the device, and verify the status light.</p></main>",
        ),
        "/manual.pdf": (
            200,
            "application/pdf",
            build_text_pdf("Pump installation and maintenance instructions"),
        ),
        "/catalog.docx": (
            200,
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            build_docx(
                paragraph("Pump catalogue", style="Heading1")
                + paragraph("Select a rated model for the installation.")
                + table(("Model", "Power"), ("P-100", "100 W"))
            ),
        ),
        "/inventory.xlsx": (
            200,
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            build_xlsx(
                {
                    "Inventory": [
                        ["Model", "Stock", "Approved"],
                        ["P-100", 12, True],
                    ]
                }
            ),
        ),
        "/feed.xml": (
            200,
            "application/xml",
            b"<?xml version=\"1.0\"?><catalog><item>"
            b"<name>P-100 pump</name><rating>100 watts</rating>"
            b"</item></catalog>",
        ),
        "/notes.txt": (
            200,
            "text/plain",
            b"Confirm isolation before beginning installation work.",
        ),
        "/private/secret": (200, "text/html", b"must never be requested"),
    }


@contextmanager
def golden_path_site():
    GoldenPathSiteHandler.requests = []
    GoldenPathSiteHandler.routes = _site_routes()
    server = ThreadingHTTPServer(("127.0.0.1", 0), GoldenPathSiteHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def _json_result(capsys, arguments: list[str]) -> dict:
    assert main(arguments) == 0
    captured = capsys.readouterr()
    assert captured.err == ""
    return json.loads(captured.out)


def test_credential_free_golden_path_preserves_review_and_restart_boundaries(
    tmp_path, capsys
):
    manifest = tmp_path / "crawl.json"
    dataset = tmp_path / "dataset"
    storage_root = tmp_path / "storage"
    review = tmp_path / "review.md"
    publisher_root = tmp_path / "published"

    with golden_path_site() as origin:
        assert main(
            [
                "source",
                "crawl",
                f"{origin}/",
                "--delay",
                "0",
                "--limit",
                "20",
                "--output",
                str(manifest),
            ]
        ) == 0
        assert capsys.readouterr().err == ""
        crawl = json.loads(manifest.read_text(encoding="utf-8"))
        assert crawl["count"] == 7
        assert crawl["crawl"]["skipped_robots"] == 1
        assert GoldenPathSiteHandler.requests == ["/robots.txt", "/", "/guide.html"]

        process = _json_result(
            capsys,
            [
                "source",
                "process",
                str(manifest),
                "--output",
                str(dataset),
                "--max-tokens",
                "100",
            ],
        )
        assert process["processed_count"] == 7
        assert process["failed_count"] == 0
        assert process["quality_failed_count"] >= 1

        inventory = _json_result(capsys, ["source", "inspect", str(dataset)])
        assert inventory["selected_count"] == 7
        assert inventory["source_uris_included"] is False
        assert inventory["quality_failed_count"] == process["quality_failed_count"]

        stored = _json_result(
            capsys,
            [
                "source",
                "store",
                str(dataset),
                "--storage",
                "local",
                "--local-root",
                str(storage_root),
                "--destination",
                "golden-path/run-001",
            ],
        )
        assert stored["provider"] == "local"
        assert (storage_root / "golden-path/run-001/processing-report.json").is_file()

        rendered = _json_result(
            capsys,
            [
                "source",
                "render",
                str(dataset),
                "--document-index",
                "0",
                "--output",
                str(review),
            ],
        )
        assert rendered["quality_status"] == "warning"
        assert "Quality: `warning`" in review.read_text(encoding="utf-8")

        preview = _json_result(
            capsys,
            [
                "publish",
                str(review),
                "golden-path/review",
                "--publisher",
                "local",
                "--local-root",
                str(publisher_root),
            ],
        )
        assert preview["status"] == "would_create"
        assert not (publisher_root / "golden-path/review.md").exists()

        requests_before_restart = list(GoldenPathSiteHandler.requests)
        report_before_restart = (dataset / "processing-report.json").read_bytes()
        assert main(
            [
                "source",
                "process",
                str(manifest),
                "--output",
                str(dataset),
            ]
        ) == 1
        assert "output already exists" in capsys.readouterr().err
        assert GoldenPathSiteHandler.requests == requests_before_restart
        assert (dataset / "processing-report.json").read_bytes() == report_before_restart

    assert "/private/secret" not in GoldenPathSiteHandler.requests
    for route in (
        "/manual.pdf",
        "/catalog.docx",
        "/inventory.xlsx",
        "/feed.xml",
        "/notes.txt",
    ):
        assert route in GoldenPathSiteHandler.requests
