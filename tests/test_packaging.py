from __future__ import annotations

import tomllib
from pathlib import Path

from doc_harvester import __version__


ROOT = Path(__file__).resolve().parents[1]


def test_pyproject_includes_every_public_doc_harvester_package():
    configuration = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    configured = set(configuration["tool"]["setuptools"]["packages"])
    package_root = ROOT / "src/doc_harvester"
    expected = {
        ".".join(path.relative_to(ROOT / "src").parts)
        for path in package_root.rglob("*")
        if path.is_dir() and (path / "__init__.py").is_file()
    }
    expected.add("doc_harvester")

    assert expected <= configured


def test_release_version_and_optional_heavy_dependencies_are_configured():
    configuration = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    project = configuration["project"]
    dependencies = set(project["dependencies"])
    optional = project["optional-dependencies"]

    assert project["version"] == __version__ == "0.2.0"
    assert not any(
        dependency.startswith(("pdf2image", "pytesseract", "playwright"))
        for dependency in dependencies
    )
    assert set(optional["ocr"]) == {
        "pdf2image==1.17.0",
        "pytesseract==0.3.10",
    }
    assert optional["browser"] == ["playwright==1.58.0"]
    assert set(optional["legacy"]) == {*optional["ocr"], *optional["browser"]}
