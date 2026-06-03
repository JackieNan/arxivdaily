from arxiv_local_daily.models import SummaryTemplateField, SummaryTemplateInput
from arxiv_local_daily.repositories import TemplateRepository


def _template(name: str, label: str) -> SummaryTemplateInput:
    return SummaryTemplateInput(
        name=name,
        language="Chinese",
        system_prompt="Summarize the paper using the configured fields.",
        input_scope="abstract",
        is_default=True,
        fields=[
            SummaryTemplateField(
                key="tldr",
                label=label,
                order=1,
                prompt="Give one sentence.",
                field_type="short_sentence",
                enabled=True,
            )
        ],
    )


def test_create_template_stores_fields_as_versioned_json(db):
    repo = TemplateRepository(db)

    template_id = repo.create_template(_template("default_research", "一句话结论"))
    db.commit()

    row = db.execute("SELECT * FROM summary_templates WHERE id = ?", (template_id,)).fetchone()

    assert row["name"] == "default_research"
    assert row["version"] == 1
    assert "一句话结论" in row["fields_json"]


def test_create_template_increments_version_for_same_name(db):
    repo = TemplateRepository(db)

    first_id = repo.create_template(_template("default_research", "一句话结论"))
    second_id = repo.create_template(_template("default_research", "核心方法"))
    db.commit()

    versions = db.execute(
        "SELECT version FROM summary_templates WHERE id IN (?, ?) ORDER BY version",
        (first_id, second_id),
    ).fetchall()

    assert [row["version"] for row in versions] == [1, 2]


def test_list_templates_returns_latest_versions_first(db):
    repo = TemplateRepository(db)
    repo.create_template(_template("default_research", "一句话结论"))
    latest_id = repo.create_template(_template("default_research", "核心方法"))
    db.commit()

    rows = repo.list_templates()

    assert rows[0]["id"] == latest_id
    assert rows[0]["version"] == 2
