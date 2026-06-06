from pathlib import Path

import pytest

from arxiv_local_daily.crawler.parser import (
    parse_daily_listing,
    parse_daily_listing_count,
    parse_daily_listing_date,
    parse_daily_listing_has_no_updates,
    parse_historical_listing_for_date,
    parse_listing_dates,
)


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


def test_parse_daily_listing_has_no_updates_detects_empty_category_page():
    html = """
    <div id="dlpage">
      <h3>Showing new listings for Thursday, 4 June 2026</h3>
      <p>No updates today.</p>
    </div>
    """

    assert parse_daily_listing_has_no_updates(html) is True


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


def test_parse_listing_dates_returns_unique_dates_in_document_order():
    html = """
    <div id="dlpage">
      <h3>Sat, 6 Jun 2026</h3>
      <h4>New submissions</h4>
      <h3>Fri, 5 Jun 2026</h3>
      <h4>New submissions for Fri, 5 Jun 2026</h4>
      <h3>Thu, 4 Jun 2026</h3>
    </div>
    """

    assert parse_listing_dates(html) == ["2026-06-06", "2026-06-05", "2026-06-04"]


def test_parse_historical_listing_for_date_extracts_only_requested_date_sections():
    html = """
    <div id="dlpage">
      <h3>Sat, 6 Jun 2026</h3>
      <h4>New submissions</h4>
      <dl>
        <dt><a title="Abstract" href="/abs/2606.09999">arXiv:2606.09999</a></dt>
        <dd><div class="list-title">Title: Newer Paper</div></dd>
      </dl>
      <h3>Fri, 5 Jun 2026</h3>
      <h4>New submissions</h4>
      <dl>
        <dt><a title="Abstract" href="/abs/2606.00010">arXiv:2606.00010</a></dt>
        <dd>
          <div class="list-title">Title: Historical New Paper</div>
          <div class="list-subjects"><span class="primary-subject">Artificial Intelligence (cs.AI)</span></div>
        </dd>
      </dl>
      <h4>Cross submissions</h4>
      <dl>
        <dt><a title="Abstract" href="/abs/2606.00011">arXiv:2606.00011</a></dt>
        <dd>
          <div class="list-title">Title: Historical Cross Paper</div>
          <div class="list-subjects"><span class="primary-subject">Machine Learning (cs.LG)</span></div>
        </dd>
      </dl>
      <h4>Replacement submissions</h4>
      <dl>
        <dt><a title="Abstract" href="/abs/2606.00012">arXiv:2606.00012</a></dt>
        <dd>
          <div class="list-title">Title: Historical Replacement Paper</div>
          <div class="list-subjects"><span class="primary-subject">Artificial Intelligence (cs.AI)</span></div>
        </dd>
      </dl>
      <h3>Thu, 4 Jun 2026</h3>
      <h4>New submissions</h4>
      <dl>
        <dt><a title="Abstract" href="/abs/2606.00001">arXiv:2606.00001</a></dt>
        <dd><div class="list-title">Title: Older Paper</div></dd>
      </dl>
    </div>
    """

    events = parse_historical_listing_for_date(
        html,
        date="2026-06-05",
        listing_category="cs.AI",
        source_url="https://arxiv.org/list/cs.AI/2606?skip=0&show=2000",
    )

    assert [(event.arxiv_id, event.event_type, event.primary_category, event.title) for event in events] == [
        ("2606.00010", "new", "cs.AI", "Historical New Paper"),
        ("2606.00011", "cross-list", "cs.LG", "Historical Cross Paper"),
        ("2606.00012", "replacement", "cs.AI", "Historical Replacement Paper"),
    ]


def test_parse_historical_listing_for_date_supports_event_headings_with_embedded_dates():
    html = """
    <div id="dlpage">
      <h3>New submissions for Fri, 5 Jun 2026</h3>
      <dl>
        <dt><a title="Abstract" href="/abs/2606.00010">arXiv:2606.00010</a></dt>
        <dd><div class="list-title">Title: Historical New Paper</div></dd>
      </dl>
      <h3>Cross submissions for Thu, 4 Jun 2026</h3>
      <dl>
        <dt><a title="Abstract" href="/abs/2606.00011">arXiv:2606.00011</a></dt>
        <dd><div class="list-title">Title: Wrong Date Paper</div></dd>
      </dl>
    </div>
    """

    events = parse_historical_listing_for_date(
        html,
        date="2026-06-05",
        listing_category="cs.AI",
        source_url="https://arxiv.org/list/cs.AI/2606?skip=0&show=2000",
    )

    assert [(event.arxiv_id, event.event_type) for event in events] == [("2606.00010", "new")]


def test_parse_historical_listing_for_date_can_filter_month_archive_by_category():
    html = """
    <div id="dlpage">
      <h3>Fri, 5 Jun 2026</h3>
      <h4>New submissions</h4>
      <dl>
        <dt><a title="Abstract" href="/abs/2606.00010">arXiv:2606.00010</a></dt>
        <dd>
          <div class="list-title">Title: AI Primary Paper</div>
          <div class="list-subjects"><span class="primary-subject">Artificial Intelligence (cs.AI)</span></div>
        </dd>
        <dt><a title="Abstract" href="/abs/2606.00011">arXiv:2606.00011</a></dt>
        <dd>
          <div class="list-title">Title: ML Cross Paper</div>
          <div class="list-subjects">
            <span class="primary-subject">Machine Learning (cs.LG)</span>; Artificial Intelligence (cs.AI)
          </div>
        </dd>
        <dt><a title="Abstract" href="/abs/2606.00012">arXiv:2606.00012</a></dt>
        <dd>
          <div class="list-title">Title: Other CS Paper</div>
          <div class="list-subjects"><span class="primary-subject">Computer Vision (cs.CV)</span></div>
        </dd>
      </dl>
    </div>
    """

    events = parse_historical_listing_for_date(
        html,
        date="2026-06-05",
        listing_category="cs.AI",
        source_url="https://arxiv.org/list/cs/2606?skip=0&show=2000",
        filter_category="cs.AI",
    )

    assert [(event.arxiv_id, event.primary_category, event.title) for event in events] == [
        ("2606.00010", "cs.AI", "AI Primary Paper"),
        ("2606.00011", "cs.LG", "ML Cross Paper"),
    ]


def test_parse_historical_listing_for_date_supports_pastweek_date_only_sections():
    html = """
    <div id="dlpage">
      <h3>Fri, 5 Jun 2026 (showing 2 of 2 entries )</h3>
      <dl>
        <dt><a title="Abstract" href="/abs/2606.00010">arXiv:2606.00010</a></dt>
        <dd>
          <div class="list-title">Title: Date Only Paper</div>
          <div class="list-subjects"><span class="primary-subject">Artificial Intelligence (cs.AI)</span></div>
        </dd>
      </dl>
    </div>
    """

    events = parse_historical_listing_for_date(
        html,
        date="2026-06-05",
        listing_category="cs.AI",
        source_url="https://arxiv.org/list/cs.AI/pastweek?skip=0&show=2000",
        filter_category="cs.AI",
        default_event_type="new",
    )

    assert [(event.arxiv_id, event.event_type, event.title) for event in events] == [
        ("2606.00010", "new", "Date Only Paper"),
    ]
