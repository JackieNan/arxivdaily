from arxiv_local_daily.models import (
    CrawlSourceInput,
    PaperMetadata,
    ParsedDailyEvent,
    SummaryTemplateField,
    SummaryTemplateInput,
)
from arxiv_local_daily.repositories import PaperRepository, ScoreRepository, SummaryRepository, TemplateRepository
from arxiv_local_daily.services import get_daily_pipeline_status, ingest_daily_crawl_sources, run_daily_pipeline


def _template() -> SummaryTemplateInput:
    return SummaryTemplateInput(
        name="daily_research",
        language="Chinese",
        system_prompt="Return Chinese paper triage fields as JSON.",
        input_scope="abstract",
        is_default=True,
        fields=[
            SummaryTemplateField(
                key="keywords",
                label="关键词",
                order=1,
                prompt="Return 3-5 Chinese keywords.",
                field_type="bullets",
            ),
            SummaryTemplateField(
                key="tldr",
                label="一句话总结",
                order=2,
                prompt="Return a Chinese one-sentence summary.",
                field_type="short_sentence",
            ),
        ],
    )


def _seed_daily_paper(db, arxiv_id: str, *, metadata_status: str = "complete") -> None:
    paper_repo = PaperRepository(db)
    paper_repo.upsert_daily_event(
        date="2026-06-03",
        event=ParsedDailyEvent(
            arxiv_id=arxiv_id,
            event_type="new",
            listing_category="cs.AI",
            primary_category="cs.AI",
            source_url="https://arxiv.org/list/cs.AI/new",
        ),
    )
    if metadata_status == "complete":
        paper_repo.upsert_metadata(
            PaperMetadata(
                arxiv_id=arxiv_id,
                title=f"Daily Pipeline Paper {arxiv_id}",
                abstract="This paper tests daily summary completion.",
                authors=["Ada Lovelace"],
                primary_category="cs.AI",
                categories=["cs.AI"],
            )
        )
    else:
        paper_repo.mark_metadata_status(arxiv_id, metadata_status, error="metadata unavailable")


def test_daily_pipeline_status_reports_summary_and_score_coverage(db):
    template_id = TemplateRepository(db).create_template(_template())
    _seed_daily_paper(db, "2606.00001")
    _seed_daily_paper(db, "2606.00002")
    _seed_daily_paper(db, "2606.00003", metadata_status="pending")
    SummaryRepository(db).upsert_summary(
        arxiv_id="2606.00001",
        template_id=template_id,
        template_version=1,
        model="fake-model",
        language="Chinese",
        input_scope="abstract",
        content={"keywords": ["每日总结"], "tldr": "已有中文总结。"},
        status="complete",
    )
    ScoreRepository(db).upsert_score(
        arxiv_id="2606.00001",
        model="fake-model",
        rubric_version="reading_priority_v1",
        content={
            "score_total": 90,
            "score_relevance": 30,
            "score_novelty": 18,
            "score_technical_depth": 18,
            "score_evidence": 12,
            "score_actionability": 12,
            "recommended_action": "read",
            "rationale": "Relevant.",
        },
        status="complete",
    )
    db.commit()

    status = get_daily_pipeline_status(
        db,
        date="2026-06-03",
        template_id=template_id,
        model="fake-model",
    )

    assert status["status"] == "partial"
    assert status["metadata"] == {
        "total": 3,
        "complete": 2,
        "pending": 1,
        "failed": 0,
        "retryable": 0,
    }
    assert status["summary"]["eligible"] == 2
    assert status["summary"]["complete"] == 1
    assert status["summary"]["missing"] == 1
    assert status["summary"]["failed"] == 0
    assert status["summary"]["template_id"] == template_id
    assert status["summary"]["required_fields"] == ["keywords", "tldr"]
    assert status["score"]["eligible"] == 2
    assert status["score"]["complete"] == 1
    assert status["score"]["missing"] == 1
    assert "metadata_pending" in status["blockers"]
    assert "summary_missing" in status["blockers"]
    assert "score_missing" in status["blockers"]


def test_run_daily_pipeline_runs_summary_and_score_after_metadata(db):
    calls: list[str] = []
    template_id = TemplateRepository(db).create_template(_template())

    def fake_crawl_runner(connection, *, date: str, categories: list[str] | None) -> int:
        calls.append("crawl")
        run_id = ingest_daily_crawl_sources(
            connection,
            date=date,
            mode="all-categories",
            sources=[
                CrawlSourceInput(
                    category="cs.AI",
                    url="https://arxiv.org/list/cs.AI/new",
                    status="complete",
                    http_status=200,
                )
            ],
        )
        _seed_daily_paper(connection, "2606.00001")
        return run_id

    def fake_metadata_runner(connection, *, date: str, limit: int | None, oai_max_pages: int):
        calls.append("metadata")
        return {"run_id": 12, "status": "complete", "merged": 1, "missing_after_merge": 0}

    def fake_summary_runner(
        connection,
        *,
        date: str,
        template_id: int | None,
        template_name: str | None,
        model: str,
        limit: int | None,
        force: bool,
    ):
        calls.append("summary")
        SummaryRepository(connection).upsert_summary(
            arxiv_id="2606.00001",
            template_id=template_id,
            template_version=1,
            model=model,
            language="Chinese",
            input_scope="abstract",
            content={"keywords": ["每日总结"], "tldr": "自动总结完成。"},
            status="complete",
        )
        connection.commit()
        return {"requested": 1, "completed": 1, "failed": 0, "skipped": 0, "template_id": template_id}

    def fake_score_runner(connection, *, date: str, model: str, limit: int | None, force: bool):
        calls.append("score")
        ScoreRepository(connection).upsert_score(
            arxiv_id="2606.00001",
            model=model,
            rubric_version="reading_priority_v1",
            content={
                "score_total": 91,
                "score_relevance": 30,
                "score_novelty": 18,
                "score_technical_depth": 18,
                "score_evidence": 12,
                "score_actionability": 13,
                "recommended_action": "read",
                "rationale": "Relevant.",
            },
            status="complete",
        )
        connection.commit()
        return {"requested": 1, "completed": 1, "failed": 0, "skipped": 0}

    result = run_daily_pipeline(
        db,
        date="2026-06-03",
        template_id=template_id,
        model="fake-model",
        crawl_runner=fake_crawl_runner,
        metadata_runner=fake_metadata_runner,
        summary_runner=fake_summary_runner,
        score_runner=fake_score_runner,
    )

    assert calls == ["crawl", "metadata", "summary", "score"]
    assert result["status"] == "complete"
    assert result["steps"]["crawl"]["run_id"] is not None
    assert result["steps"]["metadata"]["merged"] == 1
    assert result["steps"]["summary"]["completed"] == 1
    assert result["steps"]["score"]["completed"] == 1
    assert result["daily_status"]["summary"]["complete"] == 1
    assert result["daily_status"]["score"]["complete"] == 1
