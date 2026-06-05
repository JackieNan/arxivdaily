import re
from bs4 import BeautifulSoup, Tag

from arxiv_local_daily.models import ParsedDailyEvent

CATEGORY_RE = re.compile(r"\(([a-z]+(?:-[a-z]+)*(?:\.[A-Za-z0-9-]+)?)\)")
COUNT_RE = re.compile(r"\bof\s+([0-9,]+)\s+entr(?:y|ies)\b", re.IGNORECASE)
NO_UPDATES_RE = re.compile(r"\bno\s+updates\s+today\b", re.IGNORECASE)
LISTING_DATE_RE = re.compile(r"\bfor\s+(?:[A-Za-z]+,\s+)?([0-9]{1,2})\s+([A-Za-z]+)\s+([0-9]{4})\b")
BARE_LISTING_DATE_RE = re.compile(r"^(?:[A-Za-z]+,\s+)?([0-9]{1,2})\s+([A-Za-z]+)\s+([0-9]{4})\b")
MONTHS = {
    "jan": "01",
    "january": "01",
    "feb": "02",
    "february": "02",
    "mar": "03",
    "march": "03",
    "apr": "04",
    "april": "04",
    "may": "05",
    "jun": "06",
    "june": "06",
    "jul": "07",
    "july": "07",
    "aug": "08",
    "august": "08",
    "sep": "09",
    "sept": "09",
    "september": "09",
    "oct": "10",
    "october": "10",
    "nov": "11",
    "november": "11",
    "dec": "12",
    "december": "12",
}


def _heading_to_event_type(text: str) -> str | None:
    normalized = " ".join(text.lower().replace("-", " ").split())
    if "new submission" in normalized:
        return "new"
    if "cross" in normalized and ("submission" in normalized or "list" in normalized):
        return "cross-list"
    if "replacement" in normalized:
        return "replacement"
    return None


def _heading_to_date(text: str) -> str | None:
    for pattern in [LISTING_DATE_RE, BARE_LISTING_DATE_RE]:
        match = pattern.search(text)
        if not match:
            continue
        day, month_text, year = match.groups()
        month = MONTHS.get(month_text.lower())
        if month is None:
            continue
        return f"{year}-{month}-{int(day):02d}"
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


def _extract_listing_title(dd: Tag | None) -> str | None:
    if dd is None:
        return None
    title = dd.select_one(".list-title")
    if title is None:
        return None
    text = title.get_text(" ", strip=True)
    if text.lower().startswith("title:"):
        text = text.split(":", 1)[1].strip()
    return " ".join(text.split()) or None


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
                title=_extract_listing_title(dd),
                source_url=source_url,
            )
        )
    return events


def parse_daily_listing_count(html: str) -> int | None:
    soup = BeautifulSoup(html, "html.parser")
    totals: list[int] = []
    for heading in soup.select("h2, h3, h4"):
        text = heading.get_text(" ", strip=True)
        match = COUNT_RE.search(text)
        if match:
            totals.append(int(match.group(1).replace(",", "")))
    return sum(totals) if totals else None


def parse_daily_listing_has_no_updates(html: str) -> bool:
    soup = BeautifulSoup(html, "html.parser")
    text = soup.get_text(" ", strip=True)
    return bool(NO_UPDATES_RE.search(text))


def parse_daily_listing_date(html: str) -> str | None:
    dates = parse_listing_dates(html)
    unique_dates = sorted(dict.fromkeys(dates))
    return unique_dates[0] if len(unique_dates) == 1 else None


def parse_listing_dates(html: str) -> list[str]:
    soup = BeautifulSoup(html, "html.parser")
    dates: list[str] = []
    for heading in soup.select("h2, h3, h4"):
        text = heading.get_text(" ", strip=True)
        date = _heading_to_date(text)
        if date is not None:
            dates.append(date)
    return list(dict.fromkeys(dates))


def parse_historical_listing_for_date(
    html: str,
    *,
    date: str,
    listing_category: str,
    source_url: str,
) -> list[ParsedDailyEvent]:
    soup = BeautifulSoup(html, "html.parser")
    dlpage = soup.select_one("#dlpage") or soup
    events: list[ParsedDailyEvent] = []
    current_date_matches = False
    current_event_type: str | None = None

    for node in dlpage.descendants:
        if not isinstance(node, Tag):
            continue
        if node.name in {"h2", "h3", "h4"}:
            text = node.get_text(" ", strip=True)
            heading_date = _heading_to_date(text)
            detected_event_type = _heading_to_event_type(text)
            if heading_date is not None:
                current_date_matches = heading_date == date
                current_event_type = detected_event_type if current_date_matches else None
                continue
            if detected_event_type is not None:
                current_event_type = detected_event_type if current_date_matches else None
                continue
        if node.name != "dt" or not current_date_matches or current_event_type is None:
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
                title=_extract_listing_title(dd),
                source_url=source_url,
            )
        )
    return events
