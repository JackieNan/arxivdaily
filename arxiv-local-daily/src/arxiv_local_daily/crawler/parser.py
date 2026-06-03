import re
from bs4 import BeautifulSoup, Tag

from arxiv_local_daily.models import ParsedDailyEvent

CATEGORY_RE = re.compile(r"\(([a-z]+(?:-[a-z]+)*(?:\.[A-Za-z0-9-]+)?)\)")


def _heading_to_event_type(text: str) -> str | None:
    normalized = " ".join(text.lower().replace("-", " ").split())
    if "new submission" in normalized:
        return "new"
    if "cross" in normalized and ("submission" in normalized or "list" in normalized):
        return "cross-list"
    if "replacement" in normalized:
        return "replacement"
    return None


def _extract_arxiv_id(dt: Tag) -> str | None:
    abstract_link = dt.select_one("a[title='Abstract']")
    if abstract_link is None:
        return None
    href = abstract_link.get("href", "")
    if "/abs/" not in href:
        return None
    return href.split("/abs/", 1)[1].strip()


def _extract_primary_category(dd: Tag | None) -> str | None:
    if dd is None:
        return None
    primary = dd.select_one(".primary-subject")
    subject_text = primary.get_text(" ", strip=True) if primary else dd.get_text(" ", strip=True)
    match = CATEGORY_RE.search(subject_text)
    return match.group(1) if match else None


def parse_daily_listing(
    html: str,
    *,
    listing_category: str,
    source_url: str,
) -> list[ParsedDailyEvent]:
    soup = BeautifulSoup(html, "html.parser")
    dlpage = soup.select_one("#dlpage") or soup
    events: list[ParsedDailyEvent] = []
    current_event_type: str | None = None

    for node in dlpage.descendants:
        if not isinstance(node, Tag):
            continue
        if node.name in {"h2", "h3", "h4"}:
            detected = _heading_to_event_type(node.get_text(" ", strip=True))
            if detected is not None:
                current_event_type = detected
            continue
        if node.name != "dt" or current_event_type is None:
            continue
        arxiv_id = _extract_arxiv_id(node)
        if arxiv_id is None:
            continue
        dd = node.find_next_sibling("dd")
        events.append(
            ParsedDailyEvent(
                arxiv_id=arxiv_id,
                event_type=current_event_type,
                listing_category=listing_category,
                primary_category=_extract_primary_category(dd),
                source_url=source_url,
            )
        )
    return events
