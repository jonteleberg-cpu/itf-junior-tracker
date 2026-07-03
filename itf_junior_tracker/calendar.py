from __future__ import annotations

import re
from pathlib import Path
from urllib.parse import urljoin

from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright

from .models import Tournament

BASE_URL = "https://www.itftennis.com"
CALENDAR_URL = (
    BASE_URL
    + "/en/tournament-calendar/world-tennis-tour-juniors-calendar/"
    + "?categories=All&startdate=2026"
)


def category_from_url(url: str) -> str:
    m = re.search(r"/(j\d+)[-/]", url.lower())
    return m.group(1).upper() if m else ""


def acceptance_url(url: str) -> str:
    clean = url.split("#")[0].rstrip("/")
    if clean.endswith("/acceptance-list"):
        return clean + "/"
    if "/acceptance-list/" in clean:
        return clean
    return clean + "/acceptance-list/"


def fetch_calendar_html(headless: bool = True, debug_dir: str | Path | None = None) -> str:
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=headless)
        page = browser.new_page()
        page.goto(CALENDAR_URL, wait_until="networkidle", timeout=60000)
        page.wait_for_timeout(5000)
        html = page.content()
        browser.close()

    if debug_dir:
        debug = Path(debug_dir)
        debug.mkdir(parents=True, exist_ok=True)
        (debug / "calendar.html").write_text(html, encoding="utf-8")

    return html


def parse_tournaments(html: str) -> list[Tournament]:
    soup = BeautifulSoup(html, "lxml")
    tournaments = []
    seen = set()

    for a in soup.find_all("a", href=True):
        href = a["href"]

        if "/tournament/" not in href:
            continue
        if "/players/" in href:
            continue
        if "/tournament-calendar/" in href:
            continue

        url = urljoin(BASE_URL, href).split("#")[0].rstrip("/") + "/"

        if "/acceptance-list/" in url:
            url = url.split("/acceptance-list/")[0].rstrip("/") + "/"

        if url in seen:
            continue
        seen.add(url)

        name = a.get_text(" ", strip=True)
        if not name:
            parts = [x for x in url.split("/") if x]
            name = parts[4].replace("-", " ").title() if len(parts) > 4 else url

        tournaments.append(
            Tournament(
                name=name,
                url=url,
                acceptance_url=acceptance_url(url),
                category=category_from_url(url),
            )
        )

    return tournaments


def get_tournaments(headless: bool = True, debug_dir: str | Path | None = None) -> list[Tournament]:
    html = fetch_calendar_html(headless=headless, debug_dir=debug_dir)
    tournaments = parse_tournaments(html)

    if debug_dir:
        debug = Path(debug_dir)
        debug.mkdir(parents=True, exist_ok=True)
        lines = []
        for t in tournaments:
            lines.append(f"{t.category}\t{t.name}\t{t.acceptance_url}")
        (debug / "tournament_urls.txt").write_text("\n".join(lines), encoding="utf-8")

    return tournaments
