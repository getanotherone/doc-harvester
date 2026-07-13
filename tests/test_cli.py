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
        "publish": ["publish", "README.md", "docs/readme"],
        "profile": ["profile", "list"],
        "api": ["api"],
        "demo": ["demo"],
    }
    for command, argv in invocations.items():
        args = parser.parse_args(argv)
        assert args.command == command


def test_cli_accepts_installed_publisher_name():
    args = build_parser().parse_args(
        ["publish", "README.md", "remote-page", "--publisher", "third-party-docs"]
    )
    assert args.publisher == "third-party-docs"


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


def test_profile_validate_command(tmp_path, capsys):
    profile = tmp_path / "test.json"
    profile.write_text('{"queries": ["catalogue pdf"]}', encoding="utf-8")

    assert main(["profile", "validate", str(profile)]) == 0
    assert json.loads(capsys.readouterr().out)["valid"] is True


def test_local_storage_and_publisher_commands(tmp_path):
    source_dir = tmp_path / "dataset"
    source_dir.mkdir()
    (source_dir / "chunk.json").write_text("{}", encoding="utf-8")
    storage_root = tmp_path / "storage"
    assert main(
        [
            "upload",
            str(source_dir),
            "--storage",
            "local",
            "--local-root",
            str(storage_root),
            "--destination",
            "demo",
        ]
    ) == 0
    assert (storage_root / "demo/chunk.json").exists()

    source_doc = tmp_path / "guide.md"
    source_doc.write_text("guide", encoding="utf-8")
    publish_root = tmp_path / "published"
    assert main(
        [
            "publish",
            str(source_doc),
            "guide/start",
            "--publisher",
            "local",
            "--local-root",
            str(publish_root),
            "--apply",
        ]
    ) == 0
    assert (publish_root / "guide/start.md").read_text() == "guide"
