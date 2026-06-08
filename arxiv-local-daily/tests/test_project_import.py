import tomllib
from pathlib import Path


def test_package_imports():
    import arxiv_local_daily

    assert arxiv_local_daily.__version__ == "0.1.0"


def test_pyproject_includes_web_static_assets_as_package_data() -> None:
    project_root = Path(__file__).resolve().parents[1]
    pyproject = tomllib.loads((project_root / "pyproject.toml").read_text())

    package_data = pyproject["tool"]["setuptools"]["package-data"]["arxiv_local_daily"]

    assert "web/*.html" in package_data
    assert "web/*.js" in package_data
    assert "web/*.css" in package_data
