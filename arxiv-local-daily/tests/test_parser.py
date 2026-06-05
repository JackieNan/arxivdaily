from pathlib import Path

import pytest

from arxiv_local_daily.crawler.parser import parse_daily_listing, parse_daily_listing_count, parse_daily_listing_date


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


def test_parse_daily_listing_extracts_listing_title():
    html = Path("tests/fixtures/list_cs_ai_new.html").read_text()

    events = parse_daily_listing(
        html,
        listing_category="cs.AI",
        source_url="https://arxiv.org/list/cs.AI/new",
    )

    assert [event.title for event in events] == [
        "First AI Paper",
        "Cross Listed Paper",
        "Replacement Paper",
    ]


def test_parse_daily_listing_count_extracts_declared_total_entries():
    html = """
    <div id="dlpage">
      <h3>New submissions (showing 1 of 25 entries)</h3>
      <h3>Cross submissions (showing 1 of 3 entries)</h3>
      <h3>Replacement submissions (showing 1 of 2 entries)</h3>
    </div>
    """

    assert parse_daily_listing_count(html) == 30


def test_parse_daily_listing_count_returns_none_when_total_is_absent():
    html = Path("tests/fixtures/list_cs_ai_new.html").read_text()

    assert parse_daily_listing_count(html) is None


def test_parse_daily_listing_date_extracts_page_announcement_date():
    html = Path("tests/fixtures/list_cs_ai_new.html").read_text()

    assert parse_daily_listing_date(html) == "2026-06-03"


def test_parse_daily_listing_handles_single_articles_dl_with_section_headings():
    html = """
    <div id="dlpage">
      <dl id="articles">
        <h3>New submissions (showing 1 of 1 entries)</h3>
        <dt>
          <span class="list-identifier"><a title="Abstract" href="/abs/2606.00001">arXiv:2606.00001</a></span>
        </dt>
        <dd>
          <div class="list-subjects">
            <span class="primary-subject">Artificial Intelligence (cs.AI)</span>
          </div>
        </dd>
        <h3>Cross submissions (showing 1 of 1 entries)</h3>
        <dt>
          <span class="list-identifier"><a title="Abstract" href="/abs/2606.00002">arXiv:2606.00002</a></span>
        </dt>
        <dd>
          <div class="list-subjects">
            <span class="primary-subject">Machine Learning (cs.LG)</span>
          </div>
        </dd>
        <h3>Replacement submissions (showing 1 of 1 entries)</h3>
        <dt>
          <span class="list-identifier"><a title="Abstract" href="/abs/2606.00003">arXiv:2606.00003</a></span>
        </dt>
        <dd>
          <div class="list-subjects">
            <span class="primary-subject">Artificial Intelligence (cs.AI)</span>
          </div>
        </dd>
      </dl>
    </div>
    """

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


def test_parse_daily_listing_preserves_legacy_arxiv_id_namespace():
    html = """
    <div id="dlpage">
      <h3>New submissions for Wed, 3 Jun 2026</h3>
      <dl>
        <dt>
          <span class="list-identifier"><a title="Abstract" href="/abs/hep-th/9901001">arXiv:hep-th/9901001</a></span>
        </dt>
        <dd>
          <div class="list-subjects">
            <span class="primary-subject">High Energy Physics - Theory (hep-th)</span>
          </div>
        </dd>
      </dl>
    </div>
    """

    events = parse_daily_listing(
        html,
        listing_category="hep-th",
        source_url="https://arxiv.org/list/hep-th/new",
    )

    assert events[0].arxiv_id == "hep-th/9901001"


@pytest.mark.parametrize(
    "category",
    ["hep-th", "quant-ph", "physics.data-an", "cond-mat.mtrl-sci"],
)
def test_parse_daily_listing_extracts_non_cs_category_formats(category):
    html = f"""
    <div id="dlpage">
      <h3>New submissions for Wed, 3 Jun 2026</h3>
      <dl>
        <dt>
          <span class="list-identifier"><a title="Abstract" href="/abs/2606.00004">arXiv:2606.00004</a></span>
        </dt>
        <dd>
          <div class="list-subjects">
            <span class="primary-subject">Primary Subject ({category})</span>
          </div>
        </dd>
      </dl>
    </div>
    """

    events = parse_daily_listing(
        html,
        listing_category=category,
        source_url=f"https://arxiv.org/list/{category}/new",
    )

    assert events[0].primary_category == category
