from pathlib import Path

from arxiv_local_daily.crawler.parser import parse_daily_listing


def test_parse_daily_listing_extracts_all_event_types():
    html = Path("tests/fixtures/list_cs_ai_new.html").read_text()

    events = parse_daily_listing(
        html,
        listing_category="cs.AI",
        source_url="https://arxiv.org/list/cs.AI/new",
    )

    assert [(event.arxiv_id, event.event_type) for event in events] == [
        ("2606.00001", "new"),
        ("2606.00002", "cross-list"),
        ("2606.00003", "replacement"),
    ]


def test_parse_daily_listing_extracts_primary_category():
    html = Path("tests/fixtures/list_cs_ai_new.html").read_text()

    events = parse_daily_listing(
        html,
        listing_category="cs.AI",
        source_url="https://arxiv.org/list/cs.AI/new",
    )

    assert events[0].primary_category == "cs.AI"
    assert events[1].primary_category == "cs.LG"
