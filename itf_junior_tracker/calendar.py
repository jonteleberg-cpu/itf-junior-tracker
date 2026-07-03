from __future__ import annotations

import re
from datetime import date
from pathlib import Path
from urllib.parse import urljoin

from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright

from .models import Tournament

BASE_URL = "https://www.itftennis.com"


def calendar_url(start: date) -> str:
    return (
        BASE_URL
        + "/en/tournament-calendar/world-tennis-tour-juniors-calendar/"
        + f"?categories=All&startdate={start.isoformat()}"
    )


def category_from_url(url: str) -> str:
    m = re.search(r"/(j\d+)[-/]", url.lower())
    return m.group(1).upper() if m else ""


def clean_tournament_url(url: str) -> str:
    url = url.split("#")[0]
    for suffix in [
        "/acceptance-list/",
        "/draws-and-results/",
        "/fact-sheet/",
        "/order-of-play/",
        "/media-and-resources/",
    ]:
        if suffix in url:
            url = url.split(suffix)[0] + "/"
    return url.rstrip("/") + "/"


def acceptance_url(url: str) -> str:
    return clean_tournament_url(url).rstrip("/") + "/acceptance-list/"


def fetch_calendar_html(start: date, debug_dir: Path) -> str:
    url = calendar_url(start)
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto(url, wait_until="networkidle", timeout=60000)
        page.wait_for_timeout(7000)
        html = page.content()
        browser.close()

    debug_dir.mkdir(parents=True, exist_ok=True)
    (debug_dir / "calendar_url.txt").write_text(url, encoding="utf-8")
    (debug_dir / "calendar.html").write_text(html, encoding="utf-8")
    return html


def parse_tournaments(html: str, debug_dir: Path) -> list[Tournament]:
    soup = BeautifulSoup(html, "lxml")
    tournaments: list[Tournament] = []
    seen: set[str] = set()

    for a in soup.find_all("a", href=True):
        href = a["href"]

        if "/tournament/" not in href:
            continue
        if "/players/" in href or "/tournament-calendar/" in href:
            continue

        full_url = clean_tournament_url(urljoin(BASE_URL, href))

        if "/en/tournament/" not in full_url:
            continue

        category = category_from_url(full_url)
        if not category:
            continue

        if full_url in seen:
            continue
        seen.add(full_url)

        name = a.get_text(" ", strip=True)
        if not name:
            parts = [x for x in full_url.split("/") if x]
            name = parts[4].replace("-", " ").title() if len(parts) > 4 else full_url

        tournaments.append(
            Tournament(
                name=name,
                url=full_url,
                acceptance_url=acceptance_url(full_url),
                category=category,
            )
        )

    debug_dir.mkdir(parents=True, exist_ok=True)
    (debug_dir / "tournament_urls.txt").write_text(
        "\n".join(f"{t.category}\t{t.name}\t{t.acceptance_url}" for t in tournaments),
        encoding="utf-8",
    )
    return tournaments


def get_tournaments(start: date, debug_dir: Path) -> list[Tournament]:
    html = fetch_calendar_html(start=start, debug_dir=debug_dir)
    return parse_tournaments(html, debug_dir)
