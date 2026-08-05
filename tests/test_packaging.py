from __future__ import annotations

import tomllib
from pathlib import Path


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
