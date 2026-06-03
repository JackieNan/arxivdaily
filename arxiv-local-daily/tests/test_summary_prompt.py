import json

import pytest

from arxiv_local_daily.summary import SummaryParseError, build_summary_messages, parse_summary_response


def _template_row() -> dict:
    return {
        "id": 1,
        "name": "research_default",
        "language": "Chinese",
        "version": 3,
        "fields_json": json.dumps(
            [
                {
                    "key": "tldr",
                    "label": "一句话结论",
                    "order": 1,
                    "prompt": "Give one sentence about the main result.",
                    "field_type": "short_sentence",
                    "enabled": True,
                },
                {
                    "key": "method",
                    "label": "核心方法",
                    "order": 2,
                    "prompt": "Explain the core method in two bullets.",
                    "field_type": "bullets",
                    "enabled": True,
                },
                {
                    "key": "disabled_note",
                    "label": "不启用",
                    "order": 3,
                    "prompt": "Do not include this field.",
                    "field_type": "short_sentence",
                    "enabled": False,
                },
            ],
            ensure_ascii=False,
        ),
        "system_prompt": "You summarize research papers for a local reading database.",
        "input_scope": "abstract",
    }


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
        "published_at": "2026-06-03T00:00:00Z",
        "updated_at": "2026-06-03T01:00:00Z",
    }


def test_build_summary_messages_uses_enabled_template_fields_and_paper_metadata():
    messages = build_summary_messages(paper=_paper_row(), template=_template_row())

    assert messages[0]["role"] == "system"
    assert "valid JSON object" in messages[0]["content"]
    user_message = messages[1]["content"]
    assert "Structured Summaries for Daily Research" in user_message
    assert "Ada Lovelace, Alan Turing" in user_message
    assert "tldr" in user_message
    assert "method" in user_message
    assert "disabled_note" not in user_message
    assert "This paper proposes configurable summaries" in user_message


def test_parse_summary_response_accepts_fenced_json_and_filters_expected_keys():
    content = parse_summary_response(
        """```json
        {"tldr": "Useful for triage.", "method": ["Template fields"], "extra": "ignored"}
        ```""",
        expected_keys=["tldr", "method"],
    )

    assert content == {"tldr": "Useful for triage.", "method": ["Template fields"]}


def test_parse_summary_response_rejects_non_json_text():
    with pytest.raises(SummaryParseError):
        parse_summary_response("This is not JSON.", expected_keys=["tldr"])
