import sqlite3
from collections import defaultdict
from typing import Any

from arxiv_local_daily.repositories import CrawlRepository


def _unique_sorted(values: list[str] | None) -> list[str]:
    if not values:
        return []
    return sorted(dict.fromkeys(values))


def _effective_category_status(category: str, rows: list[dict[str, Any]]) -> dict[str, Any]:
    complete_rows = [row for row in rows if row["status"] == "complete"]
    if complete_rows:
        row = complete_rows[-1]
        return {
            "category": category,
            "status": "complete",
            "run_id": row["run_id"],
            "parsed_count": row["parsed_count"],
            "expected_count": row["expected_count"],
            "missing_count": row["missing_count"],
            "http_status": row["http_status"],
            "error": None,
        }
    incomplete_rows = [row for row in rows if row["status"] == "incomplete"]
    if incomplete_rows:
        row = incomplete_rows[-1]
        return {
            "category": category,
            "status": "incomplete",
            "run_id": row["run_id"],
            "parsed_count": row["parsed_count"],
            "expected_count": row["expected_count"],
            "missing_count": row["missing_count"],
            "http_status": row["http_status"],
            "error": row["error"] or "parsed count below expected count",
        }
    if rows:
        row = rows[-1]
        return {
            "category": category,
            "status": "failed",
            "run_id": row["run_id"],
            "parsed_count": row["parsed_count"],
            "expected_count": row["expected_count"],
            "missing_count": row["missing_count"],
            "http_status": row["http_status"],
            "error": row["error"],
        }
    return {
        "category": category,
        "status": "missing",
        "run_id": None,
        "parsed_count": 0,
        "expected_count": None,
        "missing_count": 0,
        "http_status": None,
        "error": "not attempted",
    }


def build_crawl_completeness_report(
    connection: sqlite3.Connection,
    *,
    date: str,
    expected_categories: list[str] | None = None,
) -> dict[str, Any]:
    source_rows = CrawlRepository(connection).list_source_rows_for_date(date)
    source_rows = [row for row in source_rows if row["run_mode"] != "historical-oai"]
    rows_by_category: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in source_rows:
        rows_by_category[row["category"]].append(row)

    attempted_categories = _unique_sorted(list(rows_by_category))
    expected = _unique_sorted(expected_categories)
    if expected:
        report_categories = _unique_sorted(expected + attempted_categories)
    else:
        report_categories = attempted_categories

    category_reports = [
        _effective_category_status(category, rows_by_category.get(category, []))
        for category in report_categories
    ]
    complete_categories = [
        category["category"] for category in category_reports if category["status"] == "complete"
    ]
    failed_categories = [
        category["category"] for category in category_reports if category["status"] == "failed"
    ]
    incomplete_categories = [
        category["category"] for category in category_reports if category["status"] == "incomplete"
    ]
    missing_categories = [
        category["category"] for category in category_reports if category["status"] == "missing"
    ]
    retry_categories = _unique_sorted(failed_categories + incomplete_categories + missing_categories)
    run_ids = sorted({int(row["run_id"]) for row in source_rows})

    if not source_rows and not expected:
        status = "no_run"
    elif retry_categories:
        status = "partial"
    else:
        status = "complete"

    return {
        "date": date,
        "status": status,
        "run_count": len(run_ids),
        "latest_run_id": run_ids[-1] if run_ids else None,
        "source_count": len(source_rows),
        "expected_category_count": len(expected) if expected else len(attempted_categories),
        "attempted_category_count": len(attempted_categories),
        "complete_category_count": len(complete_categories),
        "failed_category_count": len(failed_categories),
        "incomplete_category_count": len(incomplete_categories),
        "missing_category_count": len(missing_categories),
        "complete_categories": complete_categories,
        "failed_categories": failed_categories,
        "incomplete_categories": incomplete_categories,
        "missing_categories": missing_categories,
        "retry_categories": retry_categories,
        "categories": category_reports,
    }
