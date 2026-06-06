import json

from arxiv_local_daily.models import (
    PaperMetadata,
    ParsedDailyEvent,
    SummaryTemplateField,
    SummaryTemplateInput,
)
from arxiv_local_daily.repositories import PaperRepository, ScoreRepository, TemplateRepository
from arxiv_local_daily.services import (
    complete_ai_triage_for_date,
    generate_ai_triage_for_date,
    generate_ai_triage_for_paper,
)
from arxiv_local_daily.summary import build_ai_triage_messages, parse_ai_triage_response


class FakeTriageClient:
    def __init__(self, responses: list[str]):
        self.responses = responses
        self.calls: list[dict] = []

    def complete(self, *, model: str, messages: list[dict[str, str]]) -> str:
        self.calls.append({"model": model, "messages": messages})
        return self.responses.pop(0)


def _template_input() -> SummaryTemplateInput:
    return SummaryTemplateInput(
        name="daily_research",
        language="Chinese",
        system_prompt="Summarize papers for a Chinese research reading queue.",
        input_scope="abstract",
        is_default=True,
        fields=[
            SummaryTemplateField(
                key="keywords",
                label="关键词",
                order=1,
                prompt="提炼 5-8 个中文关键词，保留必要英文术语和 LaTeX 符号。",
                field_type="keywords",
            ),
            SummaryTemplateField(
                key="tldr",
                label="一句话结论",
                order=2,
                prompt="用一句中文概括论文的核心贡献。",
                field_type="short_sentence",
            ),
        ],
    )


def _paper_row() -> dict:
    return {
        "arxiv_id": "2606.00001",
        "title": "Structured Summaries for Daily Research",
        "abstract": "This paper proposes configurable summaries for daily research triage.",
        "authors_json": json.dumps(["Ada Lovelace", "Alan Turing"]),
        "primary_category": "cs.AI",
        "categories_json": json.dumps(["cs.AI", "cs.LG"]),
        "abs_url": "https://arxiv.org/abs/2606.00001",
        "pdf_url": "https://arxiv.org/pdf/2606.00001",
    }


def _triage_response(arxiv_id: str = "2606.00001", total: int = 88) -> str:
    return json.dumps(
        {
            "summary": {
                "keywords": ["中文关键词", "论文筛选", arxiv_id],
                "tldr": "这篇论文把每日论文筛选整理成可配置的中文摘要流程。",
            },
            "score": {
                "score_total": total,
                "score_relevance": 28,
                "score_novelty": 17,
                "score_technical_depth": 18,
                "score_evidence": 12,
                "score_actionability": 13,
                "recommended_action": "read",
                "rationale": "主题直接服务每日阅读筛选，值得优先阅读。",
            },
        },
        ensure_ascii=False,
    )


def _seed_daily_paper(
    db,
    arxiv_id: str = "2606.00001",
    *,
    category: str = "cs.AI",
    create_template: bool = True,
) -> int:
    paper_repo = PaperRepository(db)
    paper_repo.upsert_daily_event(
        date="2026-06-03",
        event=ParsedDailyEvent(
            arxiv_id=arxiv_id,
            event_type="new",
            listing_category=category,
            primary_category=category,
            source_url=f"https://arxiv.org/list/{category}/new",
        ),
    )
    paper_repo.upsert_metadata(
        PaperMetadata(
            arxiv_id=arxiv_id,
            title=f"Structured Summaries for Daily Research {arxiv_id}",
            abstract="This paper proposes configurable summaries for daily research triage.",
            authors=["Ada Lovelace", "Alan Turing"],
            primary_category=category,
            categories=[category],
            abs_url=f"https://arxiv.org/abs/{arxiv_id}",
            pdf_url=f"https://arxiv.org/pdf/{arxiv_id}",
        )
    )
    if not create_template:
        db.commit()
        return 0
    template_id = TemplateRepository(db).create_template(_template_input())
    db.commit()
    return template_id


def test_build_ai_triage_messages_requests_chinese_summary_and_score():
    template_row = {
        "id": 1,
        "name": "daily_research",
        "language": "Chinese",
        "version": 1,
        "fields_json": json.dumps([field.model_dump() for field in _template_input().fields], ensure_ascii=False),
        "system_prompt": _template_input().system_prompt,
        "input_scope": "abstract",
    }

    messages = build_ai_triage_messages(paper=_paper_row(), template=template_row)

    text = "\n".join(message["content"] for message in messages)
    assert '"summary"' in text
    assert '"score"' in text
    assert "keywords" in text
    assert "score_total" in text
    assert "Chinese" in text
    assert "Structured Summaries for Daily Research" in text


def test_parse_ai_triage_response_extracts_summary_and_score():
    parsed = parse_ai_triage_response(
        f"```json\n{_triage_response()}\n```",
        expected_summary_keys=["keywords", "tldr"],
    )

    assert parsed["summary"]["keywords"] == ["中文关键词", "论文筛选", "2606.00001"]
    assert parsed["summary"]["tldr"].startswith("这篇论文")
    assert parsed["score"]["score_total"] == 88
    assert parsed["score"]["recommended_action"] == "read"


def test_generate_ai_triage_for_date_persists_summary_and_score_with_one_llm_call(db):
    template_id = _seed_daily_paper(db)
    client = FakeTriageClient([_triage_response()])

    result = generate_ai_triage_for_date(
        db,
        date="2026-06-03",
        template_id=template_id,
        model="gpt-test",
        llm_client=client,
    )

    assert result == {
        "requested": 1,
        "completed": 1,
        "failed": 0,
        "skipped": 0,
        "template_id": template_id,
        "template_version": 1,
        "rubric_version": "reading_priority_v1",
    }
    assert len(client.calls) == 1
    assert client.calls[0]["model"] == "gpt-test"

    summary_row = db.execute("SELECT * FROM summaries WHERE arxiv_id = ?", ("2606.00001",)).fetchone()
    summary_content = json.loads(summary_row["content_json"])
    assert summary_row["status"] == "complete"
    assert summary_content["keywords"] == ["中文关键词", "论文筛选", "2606.00001"]

    score = ScoreRepository(db).get_latest_score("2606.00001")
    assert score["status"] == "complete"
    assert score["score_total"] == 88
    assert score["rationale"] == "主题直接服务每日阅读筛选，值得优先阅读。"


def test_generate_ai_triage_for_paper_persists_summary_and_score(db):
    template_id = _seed_daily_paper(db)
    client = FakeTriageClient([_triage_response()])

    result = generate_ai_triage_for_paper(
        db,
        arxiv_id="2606.00001",
        template_id=template_id,
        model="gpt-test",
        llm_client=client,
    )

    assert result == {
        "status": "complete",
        "arxiv_id": "2606.00001",
        "requested": 1,
        "completed": 1,
        "failed": 0,
        "skipped": 0,
        "template_id": template_id,
        "template_version": 1,
        "rubric_version": "reading_priority_v1",
    }
    assert len(client.calls) == 1
    assert client.calls[0]["model"] == "gpt-test"

    summary_row = db.execute("SELECT * FROM summaries WHERE arxiv_id = ?", ("2606.00001",)).fetchone()
    assert summary_row["status"] == "complete"
    assert json.loads(summary_row["content_json"])["tldr"].startswith("这篇论文")

    score = ScoreRepository(db).get_latest_score("2606.00001")
    assert score["status"] == "complete"
    assert score["score_total"] == 88


def test_generate_ai_triage_for_date_filters_candidates_by_categories(db):
    template_id = _seed_daily_paper(db, "2606.00001", category="cs.AI")
    _seed_daily_paper(db, "2606.00002", category="math.AG", create_template=False)
    client = FakeTriageClient([_triage_response("2606.00001")])

    result = generate_ai_triage_for_date(
        db,
        date="2026-06-03",
        template_id=template_id,
        model="gpt-test",
        categories=["cs.AI"],
        llm_client=client,
    )

    assert result["requested"] == 1
    assert result["completed"] == 1
    assert len(client.calls) == 1
    assert db.execute("SELECT COUNT(*) AS count FROM summaries WHERE arxiv_id = ?", ("2606.00002",)).fetchone()["count"] == 0
    assert ScoreRepository(db).get_latest_score("2606.00002") is None


def test_complete_ai_triage_for_date_runs_batches_until_all_candidates_are_done(db):
    template_id = _seed_daily_paper(db, "2606.00001")
    _seed_daily_paper(db, "2606.00002")
    _seed_daily_paper(db, "2606.00003")
    client = FakeTriageClient(
        [
            _triage_response("2606.00001", 81),
            _triage_response("2606.00002", 82),
            _triage_response("2606.00003", 83),
        ]
    )

    result = complete_ai_triage_for_date(
        db,
        date="2026-06-03",
        template_id=template_id,
        model="gpt-test",
        batch_size=2,
        max_rounds=5,
        llm_client=client,
    )

    assert result["status"] == "complete"
    assert result["rounds"] == 2
    assert result["summary"]["complete"] == 3
    assert result["score"]["complete"] == 3
    assert len(client.calls) == 3


def test_complete_ai_triage_for_date_skips_without_configured_llm_api(db, monkeypatch):
    template_id = _seed_daily_paper(db)
    monkeypatch.delenv("ARXIV_DAILY_LLM_API_KEY", raising=False)
    monkeypatch.delenv("ARXIV_DAILY_LLM_BASE_URL", raising=False)

    result = complete_ai_triage_for_date(
        db,
        date="2026-06-03",
        template_id=template_id,
        model="gpt-test",
    )

    assert result["status"] == "not_configured"
    assert result["rounds"] == 0
    assert db.execute("SELECT COUNT(*) AS count FROM summaries").fetchone()["count"] == 0
    assert db.execute("SELECT COUNT(*) AS count FROM paper_scores").fetchone()["count"] == 0
