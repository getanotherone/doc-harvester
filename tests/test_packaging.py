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

    assert project["version"] == __version__ == "0.2.1"
    assert project["license"] == "Apache-2.0"
    assert project["urls"] == {
        "Homepage": "https://github.com/getanotherone/doc-harvester",
        "Documentation": "https://github.com/getanotherone/doc-harvester/tree/main/docs",
        "Issues": "https://github.com/getanotherone/doc-harvester/issues",
        "Changelog": "https://github.com/getanotherone/doc-harvester/blob/main/CHANGELOG.md",
        "Source": "https://github.com/getanotherone/doc-harvester",
    }
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


def test_pypi_release_workflow_is_gated_and_uses_trusted_publishing():
    workflow = (ROOT / ".github/workflows/release.yml").read_text(encoding="utf-8")

    assert "types: [published]" in workflow
    assert "environment:" in workflow
    assert "name: pypi" in workflow
    assert "id-token: write" in workflow
    assert "python -m build" in workflow
    assert "python -m twine check dist/*" in workflow
    assert "pypa/gh-action-pypi-publish@release/v1" in workflow
    assert "password:" not in workflow
    assert "PYPI_TOKEN" not in workflow
