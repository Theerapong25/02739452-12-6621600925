"""Public HTML price-list scrapers; no browser automation or personal data."""
from __future__ import annotations

import re
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from urllib.parse import urljoin
from urllib.robotparser import RobotFileParser

import requests
from bs4 import BeautifulSoup

USER_AGENT = "NotebookPriceResearch/1.0 (educational project; public product listings)"
SOURCES = {
    "advice": "https://www.advice.co.th/nescen-n053/product/pricelist?cate=notebooks",
    "jib": "https://www.jib.co.th/web/product/product_list/2/25",
    "mercular": "https://www.mercular.com/computer/laptop",
}
SOURCE_PAGES = {
    "jib": [
        "https://www.jib.co.th/web/product/product_list/2/25",
        "https://www.jib.co.th/web/product/product_list/2/1338",
        "https://www.jib.co.th/web/product/product_list/2/1468",
    ]
}


@dataclass
class Listing:
    source: str
    source_id: str
    name: str
    price_baht: int
    product_url: str
    description: str
    fetched_at: str

    def to_dict(self):
        return asdict(self)


def parse_price(value: str) -> int | None:
    match = re.search(r"\d[\d,]*", value or "")
    return int(match.group().replace(",", "")) if match else None


def parse_advice(html: str, fetched_at: str) -> list[Listing]:
    soup = BeautifulSoup(html, "html.parser")
    out = []
    for row in soup.select("table.legacy-price-table tbody tr"):
        cells = row.find_all("td", recursive=False)
        if len(cells) < 3 or not cells[0].find("a"):
            continue
        link = cells[0].find("a")
        href = urljoin("https://www.advice.co.th", link.get("href", ""))
        price = parse_price(cells[2].get_text(" ", strip=True))
        source_id = href.rstrip("/").split("/")[-1]
        if price and source_id:
            out.append(Listing("advice", source_id, link.get_text(" ", strip=True), price,
                               href, cells[1].get_text(" ", strip=True), fetched_at))
    return out


def parse_jib(html: str, fetched_at: str) -> list[Listing]:
    soup = BeautifulSoup(html, "html.parser")
    out = []
    for card in soup.select(".divboxpro"):
        link = card.find("a", href=re.compile(r"/readProduct/\d+"))
        price_node = card.select_one(".price_total")
        if not link or not price_node:
            continue
        name = link.get("title") or link.get_text(" ", strip=True)
        if "NOTEBOOK" not in name.upper() and "โน้ตบุ๊ค" not in name:
            continue
        match = re.search(r"/readProduct/(\d+)", link["href"])
        price = parse_price(price_node.get_text(" ", strip=True))
        if match and price:
            out.append(Listing("jib", match.group(1), name, price, link["href"],
                               card.get_text(" ", strip=True)[:500], fetched_at))
    if out:
        return out
    # Legacy price-list layout remains supported as a fallback.
    for row in soup.select("#table_price tbody tr"):
        cells = row.find_all("td", recursive=False)
        if len(cells) < 6:
            continue
        link = cells[1].find("a", href=True)
        if not link:
            continue
        name = link.get_text(" ", strip=True)
        if "NOTEBOOK" not in name.upper() and "โน้ตบุ๊ค" not in name:
            continue
        href = link["href"]
        match = re.search(r"/readProduct/(\d+)", href)
        if not match:
            continue
        # Last price column is the current sale price; fall back to list price.
        price = parse_price(cells[5].get_text(" ", strip=True)) or parse_price(cells[3].get_text(" ", strip=True))
        if price:
            out.append(Listing("jib", match.group(1), name, price, href,
                               cells[2].get_text(" ", strip=True), fetched_at))
    return out


def parse_mercular(html: str, fetched_at: str) -> list[Listing]:
    soup = BeautifulSoup(html, "html.parser")
    out = []
    for card in soup.select(".product-card"):
        title = card.select_one(".product-title")
        link = card.find("a", href=True)
        price_nodes = [node for node in card.select("span, p")
                       if "฿" in node.get_text(" ", strip=True)]
        if not title or not link or not price_nodes:
            continue
        href = urljoin("https://www.mercular.com", link["href"])
        name = title.get_text(" ", strip=True)
        price = parse_price(price_nodes[0].get_text(" ", strip=True))
        source_id = href.rstrip("/").split("/")[-1]
        if price and source_id and "notebook" in name.lower():
            out.append(Listing("mercular", source_id, name, price, href,
                               card.get_text(" ", strip=True)[:500], fetched_at))
    return out


PARSERS = {"advice": parse_advice, "jib": parse_jib, "mercular": parse_mercular}


def fetch_source(source: str) -> tuple[list[Listing], dict]:
    url = SOURCES[source]
    origin = "/".join(url.split("/")[:3])
    robot_url = origin + "/robots.txt"
    session = requests.Session()
    session.headers.update({"User-Agent": USER_AGENT, "Accept-Language": "th-TH,th;q=0.9,en;q=0.8"})
    robots_response = session.get(robot_url, timeout=20)
    robots_response.raise_for_status()
    robot = RobotFileParser()
    robot.parse(robots_response.text.splitlines())
    pages = SOURCE_PAGES.get(source, [url])
    fetched_at = datetime.now(timezone.utc).isoformat()
    rows_by_id = {}
    page_results = []
    for index, page in enumerate(pages):
        if not robot.can_fetch(USER_AGENT, page):
            raise PermissionError(f"robots.txt disallows {page}")
        if index:
            time.sleep(1)
        response = session.get(page, timeout=35)
        response.raise_for_status()
        parsed = PARSERS[source](response.text, fetched_at)
        page_results.append({"url": page, "count": len(parsed), "http_status": response.status_code})
        for row in parsed:
            rows_by_id[row.source_id] = row
    rows = list(rows_by_id.values())
    if not rows:
        raise ValueError(f"No products parsed from {source}; HTML may have changed")
    return rows, {"source": source, "url": url, "pages": page_results,
                  "fetched_at": fetched_at, "count": len(rows)}
