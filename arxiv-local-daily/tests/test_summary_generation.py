import json

from arxiv_local_daily.models import (
    PaperMetadata,
    ParsedDailyEvent,
    SummaryTemplateField,
    SummaryTemplateInput,
)
from arxiv_local_daily.repositories import PaperRepository, TemplateRepository
from arxiv_local_daily.services import generate_summaries_for_date


class FakeLLMClient:
    def __init__(self, response: str):
        self.response = response
        self.calls: list[dict] = []

    def complete(self, *, model: str, messages: list[dict[str, str]]) -> str:
        self.calls.append({"model": model, "messages": messages})
        return self.response


class FailingLLMClient:
    def complete(self, *, model: str, messages: list[dict[str, str]]) -> str:
        raise RuntimeError("model unavailable")


def _template() -> SummaryTemplateInput:
    return SummaryTemplateInput(
        name="daily_research",
        language="Chinese",
        system_prompt="Return the configured research summary sections.",
        input_scope="abstract",
        is_default=True,
        fields=[
            SummaryTemplateField(
                key="tldr",
                label="一句话结论",
                order=1,
                prompt="Summarize the main result in one sentence.",
                field_type="short_sentence",
            ),
            SummaryTemplateField(
                key="method",
                label="核心方法",
                order=2,
                prompt="List the core method.",
                field_type="bullets",
            ),
        ],
    )


def _seed_daily_paper(db) -> int:
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
    template_id = TemplateRepository(db).create_template(_template())
    db.commit()
    return template_id


def test_generate_summaries_for_date_persists_structured_content(db):
    template_id = _seed_daily_paper(db)
    llm = FakeLLMClient(
        json.dumps(
            {
                "tldr": "A configurable summary pipeline helps daily paper triage.",
                "method": ["Versioned templates", "Structured JSON output"],
            }
        )
    )

    result = generate_summaries_for_date(
        db,
        date="2026-06-03",
        template_id=template_id,
        model="fake-model",
        llm_client=llm,
    )

    assert result == {
        "requested": 1,
        "completed": 1,
        "failed": 0,
        "skipped": 0,
        "template_id": template_id,
        "template_version": 1,
    }
    assert llm.calls[0]["model"] == "fake-model"

    row = db.execute("SELECT * FROM summaries WHERE arxiv_id = ?", ("2606.00001",)).fetchone()
    content = json.loads(row["content_json"])
    assert row["status"] == "complete"
    assert row["template_id"] == template_id
    assert row["template_version"] == 1
    assert row["model"] == "fake-model"
    assert content["tldr"].startswith("A configurable summary pipeline")
    assert content["method"] == ["Versioned templates", "Structured JSON output"]


def test_generate_summaries_for_date_defaults_to_all_candidates(db):
    template_id = _seed_daily_paper(db)
    paper_repo = PaperRepository(db)
    for index in range(2, 5):
        arxiv_id = f"2606.0000{index}"
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
        paper_repo.upsert_metadata(
            PaperMetadata(
                arxiv_id=arxiv_id,
                title=f"Structured Summary Candidate {index}",
                abstract=f"Candidate {index} abstract.",
                authors=["Ada Lovelace"],
                primary_category="cs.AI",
                categories=["cs.AI"],
            )
        )
    db.commit()
    llm = FakeLLMClient(json.dumps({"tldr": "All candidates", "method": ["No UI limit"]}))

    result = generate_summaries_for_date(
        db,
        date="2026-06-03",
        template_id=template_id,
        model="fake-model",
        llm_client=llm,
    )

    assert result["requested"] == 4
    assert result["completed"] == 4
    assert len(llm.calls) == 4


def test_generate_summaries_for_date_skips_existing_complete_summary_without_force(db):
    template_id = _seed_daily_paper(db)
    llm = FakeLLMClient(json.dumps({"tldr": "First", "method": ["First method"]}))
    generate_summaries_for_date(
        db,
        date="2026-06-03",
        template_id=template_id,
        model="fake-model",
        llm_client=llm,
    )

    result = generate_summaries_for_date(
        db,
        date="2026-06-03",
        template_id=template_id,
        model="fake-model",
        llm_client=llm,
    )

    assert result["requested"] == 0
    assert result["skipped"] == 1
    assert len(llm.calls) == 1


def test_generate_summaries_for_date_records_failed_summary_rows(db):
    template_id = _seed_daily_paper(db)

    result = generate_summaries_for_date(
        db,
        date="2026-06-03",
        template_id=template_id,
        model="fake-model",
        llm_client=FailingLLMClient(),
    )

    assert result["requested"] == 1
    assert result["completed"] == 0
    assert result["failed"] == 1
    row = db.execute("SELECT * FROM summaries WHERE arxiv_id = ?", ("2606.00001",)).fetchone()
    assert row["status"] == "failed"
    assert "model unavailable" in row["content_json"]
