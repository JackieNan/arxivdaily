def test_schema_creates_core_tables(db):
    rows = db.execute(
        "SELECT name FROM sqlite_master WHERE type = 'table' ORDER BY name"
    ).fetchall()
    table_names = {row["name"] for row in rows}

    assert {
        "ai_jobs",
        "crawl_run_sources",
        "crawl_runs",
        "daily_events",
        "papers",
        "summary_templates",
        "summaries",
    }.issubset(table_names)


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
