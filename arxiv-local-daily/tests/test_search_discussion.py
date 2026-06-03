from arxiv_local_daily.models import (
    PaperDiscussionInput,
    PaperMetadata,
    ParsedDailyEvent,
    SummaryTemplateField,
    SummaryTemplateInput,
)
from arxiv_local_daily.repositories import (
    DiscussionRepository,
    PaperRepository,
    SearchRepository,
    SummaryRepository,
    TemplateRepository,
)


def _seed_search_data(db):
    paper_repo = PaperRepository(db)
    paper_repo.upsert_daily_event(
        date="2026-06-03",
        event=ParsedDailyEvent(
            arxiv_id="2606.00001",
            event_type="new",
            listing_category="cs.AI",
            primary_category="cs.AI",
            source_url="https://arxiv.org/list/cs.AI/new",
        ),
    )
    paper_repo.upsert_metadata(
        PaperMetadata(
            arxiv_id="2606.00001",
            title="Structured Summaries for Daily Research",
            abstract="This paper proposes configurable summaries for daily research triage.",
            authors=["Ada Lovelace", "Alan Turing"],
            primary_category="cs.AI",
            categories=["cs.AI", "cs.LG"],
            abs_url="https://arxiv.org/abs/2606.00001",
            pdf_url="https://arxiv.org/pdf/2606.00001",
        )
    )
    template_id = TemplateRepository(db).create_template(
        SummaryTemplateInput(
            name="daily_research",
            language="Chinese",
            system_prompt="Summarize.",
            input_scope="abstract",
            fields=[
                SummaryTemplateField(
                    key="tldr",
                    label="一句话结论",
                    order=1,
                    prompt="Give one sentence.",
                    field_type="short_sentence",
                )
            ],
        )
    )
    SummaryRepository(db).upsert_summary(
        arxiv_id="2606.00001",
        template_id=template_id,
        template_version=1,
        model="fake-model",
        language="Chinese",
        input_scope="abstract",
        content={"tldr": "可配置总结流水线帮助每日论文筛选。", "keywords": ["论文筛选", "可配置摘要", "本地数据库"]},
        status="complete",
    )
    db.commit()


def test_discussion_repository_adds_and_lists_messages_for_paper(db):
    _seed_search_data(db)
    repo = DiscussionRepository(db)

    message_id = repo.add_message(
        "2606.00001",
        PaperDiscussionInput(role="user", content="Why is this useful?", tags=["question"]),
    )
    db.commit()

    rows = repo.list_messages("2606.00001")
    assert rows[0]["id"] == message_id
    assert rows[0]["role"] == "user"
    assert rows[0]["content"] == "Why is this useful?"
    assert rows[0]["tags"] == ["question"]


def test_search_papers_matches_metadata_and_summary_content(db):
    _seed_search_data(db)
    repo = SearchRepository(db)

    title_results = repo.search_papers(query="structured summaries")
    summary_results = repo.search_papers(query="论文筛选")

    assert [row["arxiv_id"] for row in title_results] == ["2606.00001"]
    assert [row["arxiv_id"] for row in summary_results] == ["2606.00001"]
    assert title_results[0]["latest_date"] == "2026-06-03"
    assert title_results[0]["summary_statuses"] == ["complete"]
    assert title_results[0]["summary_keywords"] == ["论文筛选", "可配置摘要", "本地数据库"]


def test_search_papers_filters_by_daily_event_and_status_fields(db):
    _seed_search_data(db)
    repo = SearchRepository(db)

    matching = repo.search_papers(
        query="论文筛选",
        date="2026-06-03",
        category="cs.AI",
        event_type="new",
        metadata_status="complete",
        summary_status="complete",
    )
    wrong_category = repo.search_papers(query="论文筛选", category="math.AG")

    assert [row["arxiv_id"] for row in matching] == ["2606.00001"]
    assert wrong_category == []


def test_get_paper_detail_returns_events_summaries_and_discussions(db):
    _seed_search_data(db)
    DiscussionRepository(db).add_message(
        "2606.00001",
        PaperDiscussionInput(role="assistant", content="This is useful for triage."),
    )
    db.commit()

    detail = SearchRepository(db).get_paper_detail("2606.00001")

    assert detail["paper"]["title"] == "Structured Summaries for Daily Research"
    assert detail["events"][0]["date"] == "2026-06-03"
    assert detail["summaries"][0]["content"]["tldr"].startswith("可配置")
    assert detail["discussions"][0]["content"] == "This is useful for triage."
