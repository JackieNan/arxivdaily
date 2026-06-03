import re

from bs4 import BeautifulSoup

CATEGORY_HEADING_RE = re.compile(r"^([a-z]+(?:-[a-z]+)*(?:\.[A-Za-z0-9-]+)?)\s+\(")


def parse_category_taxonomy(html: str) -> list[str]:
    soup = BeautifulSoup(html, "html.parser")
    categories: set[str] = set()
    for heading in soup.find_all(["h3", "h4", "li", "a"]):
        text = heading.get_text(" ", strip=True)
        match = CATEGORY_HEADING_RE.match(text)
        if match is not None:
            categories.add(match.group(1))
    return sorted(categories)
