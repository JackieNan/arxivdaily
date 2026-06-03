from pathlib import Path

from arxiv_local_daily.crawler.taxonomy import parse_category_taxonomy


def test_parse_category_taxonomy_extracts_modern_and_legacy_categories():
    html = Path("tests/fixtures/category_taxonomy.html").read_text()

    categories = parse_category_taxonomy(html)

    assert categories == ["cond-mat.mtrl-sci", "cs.AI", "cs.LG", "hep-th"]


def test_parse_category_taxonomy_deduplicates_categories():
    html = "<h4>cs.AI (Artificial Intelligence)</h4><h4>cs.AI (Artificial Intelligence)</h4>"

    categories = parse_category_taxonomy(html)

    assert categories == ["cs.AI"]
