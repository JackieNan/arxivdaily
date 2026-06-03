from arxiv_local_daily.models import PaperMetadata, ParsedDailyEvent
from arxiv_local_daily.repositories import PaperRepository, ScoreRepository, SearchRepository
from arxiv_local_daily.services import score_papers_for_date
from arxiv_local_daily.summary import build_score_messages, parse_score_response


class FakeScoringClient:
    def __init__(self, responses: list[str]):
        self.responses = responses
        self.calls: list[dict] = []

    def complete(self, *, model: str, messages: list[dict[str, str]]) -> str:
        self.calls.append({"model": model, "messages": messages})
        return self.responses.pop(0)


def _seed_paper(db, arxiv_id: str, title: str) -> None:
    repo = PaperRepository(db)
    repo.upsert_daily_event(
        date="2026-06-03",
        event=ParsedDailyEvent(
            arxiv_id=arxiv_id,
            event_type="new",
            listing_category="cs.AI",
            primary_category="cs.AI",
            title=title,
            source_url="https://arxiv.org/list/cs.AI/new",
        ),
    )
    repo.upsert_metadata(
        PaperMetadata(
            arxiv_id=arxiv_id,
            title=title,
            abstract=f"{title} abstract.",
            authors=["Ada Lovelace"],
            primary_category="cs.AI",
            categories=["cs.AI"],
        )
    )


def test_parse_score_response_validates_expected_score_fields():
    result = parse_score_response(
        """
        {
          "score_total": 86,
          "score_relevance": 28,
          "score_novelty": 16,
          "score_technical_depth": 17,
          "score_evidence": 12,
          "score_actionability": 13,
          "recommended_action": "read",
          "rationale": "Strong fit for today's reading."
        }
        """
    )

    assert result["score_total"] == 86
    assert result["recommended_action"] == "read"


def test_build_score_messages_includes_rubric_and_summary():
    messages = build_score_messages(
        paper={
            "arxiv_id": "2606.00001",
            "title": "Useful Paper",
            "abstract": "Abstract.",
            "primary_category": "cs.AI",
        },
        summary={"tldr": "Good idea.", "method": ["A", "B"]},
    )

    text = "\n".join(message["content"] for message in messages)
    assert "reading-priority score" in text
    assert "score_relevance" in text
    assert "Useful Paper" in text
    assert "Good idea." in text


def test_score_papers_for_date_persists_scores(db):
    _seed_paper(db, "2606.00001", "High Priority Paper")
    client = FakeScoringClient(
        [
            """
            {
              "score_total": 91,
              "score_relevance": 30,
              "score_novelty": 18,
              "score_technical_depth": 18,
              "score_evidence": 12,
              "score_actionability": 13,
              "recommended_action": "read",
              "rationale": "Directly relevant."
            }
            """
        ]
    )

    result = score_papers_for_date(
        db,
        date="2026-06-03",
        model="score-model",
        limit=1,
        llm_client=client,
    )

    assert result == {"requested": 1, "completed": 1, "failed": 0, "skipped": 0}
    score = ScoreRepository(db).get_latest_score("2606.00001")
    assert score is not None
    assert score["score_total"] == 91
    assert score["recommended_action"] == "read"
    assert score["rationale"] == "Directly relevant."


def test_search_papers_can_sort_by_latest_score(db):
    _seed_paper(db, "2606.00001", "Lower Score")
    _seed_paper(db, "2606.00002", "Higher Score")
    repo = ScoreRepository(db)
    repo.upsert_score(
        arxiv_id="2606.00001",
        model="score-model",
        rubric_version="reading_priority_v1",
        content={
            "score_total": 61,
            "score_relevance": 20,
            "score_novelty": 10,
            "score_technical_depth": 12,
            "score_evidence": 9,
            "score_actionability": 10,
            "recommended_action": "skim",
            "rationale": "Somewhat useful.",
        },
        status="complete",
    )
    repo.upsert_score(
        arxiv_id="2606.00002",
        model="score-model",
        rubric_version="reading_priority_v1",
        content={
            "score_total": 94,
            "score_relevance": 30,
            "score_novelty": 19,
            "score_technical_depth": 18,
            "score_evidence": 14,
            "score_actionability": 13,
            "recommended_action": "read",
            "rationale": "Very useful.",
        },
        status="complete",
    )
    db.commit()

    results = SearchRepository(db).search_papers(date="2026-06-03", sort="score")

    assert [paper["arxiv_id"] for paper in results] == ["2606.00002", "2606.00001"]
    assert results[0]["score"]["score_total"] == 94
