import json

from doc_harvester.cli import build_parser, main
from doc_harvester.demo import build_demo_result


def test_cli_exposes_public_commands():
    parser = build_parser()
    invocations = {
        "discover": ["discover", "example.com"],
        "crawl": ["crawl", "https://example.com/catalog"],
        "files": ["files", "https://example.com/downloads"],
        "upload": ["upload", "electrical/example.com"],
        "api": ["api"],
        "demo": ["demo"],
    }
    for command, argv in invocations.items():
        args = parser.parse_args(argv)
        assert args.command == command


def test_offline_demo_contract():
    result = build_demo_result()
    assert result["schema_version"] == 1
    assert result["blocks_extracted"] > 0
    assert result["chunks"]
    assert "корзину" not in "\n".join(chunk["text"] for chunk in result["chunks"])
    assert any(chunk["standard_id"] for chunk in result["chunks"])


def test_demo_command_writes_json(tmp_path):
    output = tmp_path / "demo.json"
    assert main(["demo", "--output", str(output)]) == 0
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["chunks"]
