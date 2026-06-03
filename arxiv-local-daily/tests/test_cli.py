from arxiv_local_daily.cli import parse_args


def test_parse_args_accepts_date_and_category():
    args = parse_args(["crawl", "--date", "2026-06-03", "--category", "cs.AI"])

    assert args.command == "crawl"
    assert args.date == "2026-06-03"
    assert args.category == ["cs.AI"]
