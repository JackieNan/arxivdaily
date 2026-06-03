import sqlite3

from arxiv_local_daily.crawler.http import ArxivHttpClient
from arxiv_local_daily.models import CrawlSourceInput
from arxiv_local_daily.services import ingest_daily_crawl_sources


def build_daily_listing_url(base_url: str, category: str) -> str:
    return f"{base_url.rstrip('/')}/list/{category}/new"


def run_live_daily_crawl(
    connection: sqlite3.Connection,
    *,
    date: str,
    categories: list[str],
    http_client: ArxivHttpClient | None = None,
    base_url: str = "https://arxiv.org",
) -> int:
    client = http_client or ArxivHttpClient()
    sources: list[CrawlSourceInput] = []
    for category in categories:
        url = build_daily_listing_url(base_url, category)
        try:
            response = client.fetch_text(url)
        except Exception as exc:
            sources.append(
                CrawlSourceInput(
                    category=category,
                    url=url,
                    status="failed",
                    http_status=None,
                    html=None,
                    error=str(exc),
                )
            )
            continue
        if response.status_code == 200:
            sources.append(
                CrawlSourceInput(
                    category=category,
                    url=url,
                    status="complete",
                    http_status=response.status_code,
                    html=response.text,
                )
            )
        else:
            sources.append(
                CrawlSourceInput(
                    category=category,
                    url=url,
                    status="failed",
                    http_status=response.status_code,
                    html=None,
                    error=f"HTTP {response.status_code}",
                )
            )
    return ingest_daily_crawl_sources(connection, date=date, mode="all-categories", sources=sources)
