def test_schema_creates_core_tables(db):
    rows = db.execute(
        "SELECT name FROM sqlite_master WHERE type = 'table' ORDER BY name"
    ).fetchall()
    table_names = {row["name"] for row in rows}

    assert {
        "ai_jobs",
        "crawl_run_sources",
        "crawl_runs",
        "crawl_preflight_runs",
        "crawl_preflight_sources",
        "daily_events",
        "daily_automation_runs",
        "metadata_sync_runs",
        "metadata_enrichment_runs",
        "metadata_merge_reports",
        "metadata_source_records",
        "papers",
        "paper_discussions",
        "paper_scores",
        "summary_templates",
        "summaries",
    }.issubset(table_names)

    paper_columns = {
        row["name"]
        for row in db.execute("PRAGMA table_info(papers)").fetchall()
    }
    assert {
        "metadata_error",
        "metadata_attempts",
        "metadata_next_run_at",
    }.issubset(paper_columns)


def test_daily_events_are_unique_per_date_id_type_and_listing_category(db):
    db.execute(
        """
        INSERT INTO papers (arxiv_id, metadata_status)
        VALUES (?, ?)
        """,
        ("2606.00001", "pending"),
    )
    db.execute(
        """
        INSERT INTO daily_events
            (date, arxiv_id, event_type, listing_category, seen_source_url)
        VALUES (?, ?, ?, ?, ?)
        """,
        ("2026-06-03", "2606.00001", "new", "cs.AI", "https://arxiv.org/list/cs.AI/new"),
    )

    try:
        db.execute(
            """
            INSERT INTO daily_events
                (date, arxiv_id, event_type, listing_category, seen_source_url)
            VALUES (?, ?, ?, ?, ?)
            """,
            ("2026-06-03", "2606.00001", "new", "cs.AI", "https://arxiv.org/list/cs.AI/new"),
        )
    except Exception as exc:
        assert "UNIQUE" in str(exc)
    else:
        raise AssertionError("duplicate daily event insert should fail")
