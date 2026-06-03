from arxiv_local_daily.cli import parse_args


def test_parse_args_accepts_date_and_category():
    args = parse_args(["crawl", "--date", "2026-06-03", "--category", "cs.AI"])

    assert args.command == "crawl"
    assert args.date == "2026-06-03"
    assert args.category == ["cs.AI"]


def test_parse_args_all_categories_when_category_omitted():
    args = parse_args(["crawl", "--date", "2026-06-03"])

    assert args.command == "crawl"
    assert args.date == "2026-06-03"
    assert args.category is None


def test_parse_args_accepts_metadata_date_and_limit():
    args = parse_args(["metadata", "--date", "2026-06-03", "--limit", "25"])

    assert args.command == "metadata"
    assert args.date == "2026-06-03"
    assert args.limit == 25


def test_parse_args_accepts_summarize_controls():
    args = parse_args(
        [
            "summarize",
            "--date",
            "2026-06-03",
            "--template-id",
            "7",
            "--model",
            "fake-model",
            "--limit",
            "5",
            "--force",
        ]
    )

    assert args.command == "summarize"
    assert args.date == "2026-06-03"
    assert args.template_id == 7
    assert args.model == "fake-model"
    assert args.limit == 5
    assert args.force is True


def test_parse_args_accepts_template_import_file():
    args = parse_args(["template", "import", "--file", "template.json"])

    assert args.command == "template"
    assert args.template_command == "import"
    assert args.file == "template.json"


def test_parse_args_accepts_crawl_audit_expected_categories():
    args = parse_args(
        [
            "crawl-audit",
            "--date",
            "2026-06-03",
            "--expected-category",
            "cs.AI",
            "--expected-category",
            "cs.LG",
        ]
    )

    assert args.command == "crawl-audit"
    assert args.date == "2026-06-03"
    assert args.expected_category == ["cs.AI", "cs.LG"]


def test_parse_args_accepts_crawl_retry_failed_expected_categories():
    args = parse_args(
        [
            "crawl-retry-failed",
            "--date",
            "2026-06-03",
            "--expected-category",
            "cs.AI",
        ]
    )

    assert args.command == "crawl-retry-failed"
    assert args.date == "2026-06-03"
    assert args.expected_category == ["cs.AI"]


def test_parse_args_accepts_search_filters():
    args = parse_args(
        [
            "search",
            "--query",
            "daily triage",
            "--date",
            "2026-06-03",
            "--category",
            "cs.AI",
            "--event-type",
            "new",
            "--metadata-status",
            "complete",
            "--summary-status",
            "complete",
            "--limit",
            "5",
        ]
    )

    assert args.command == "search"
    assert args.query == "daily triage"
    assert args.date == "2026-06-03"
    assert args.category == "cs.AI"
    assert args.event_type == "new"
    assert args.metadata_status == "complete"
    assert args.summary_status == "complete"
    assert args.limit == 5


def test_parse_args_accepts_discuss_add_and_list():
    add_args = parse_args(
        [
            "discuss",
            "add",
            "--arxiv-id",
            "2606.00001",
            "--role",
            "user",
            "--content",
            "Why is this useful?",
            "--tag",
            "question",
        ]
    )
    list_args = parse_args(["discuss", "list", "--arxiv-id", "2606.00001"])

    assert add_args.command == "discuss"
    assert add_args.discuss_command == "add"
    assert add_args.arxiv_id == "2606.00001"
    assert add_args.role == "user"
    assert add_args.content == "Why is this useful?"
    assert add_args.tag == ["question"]
    assert list_args.command == "discuss"
    assert list_args.discuss_command == "list"
    assert list_args.arxiv_id == "2606.00001"
