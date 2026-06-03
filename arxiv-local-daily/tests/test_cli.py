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
