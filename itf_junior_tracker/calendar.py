from __future__ import annotations
import re
from datetime import date
from pathlib import Path
from urllib.parse import urljoin
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright
from .models import Tournament

BASE_URL = "https://www.itftennis.com"
MONTHS = {
    "jan": 1, "january": 1, "feb": 2, "february": 2, "mar": 3, "march": 3,
    "apr": 4, "april": 4, "may": 5, "jun": 6, "june": 6, "jul": 7, "july": 7,
    "aug": 8, "august": 8, "sep": 9, "sept": 9, "september": 9,
    "oct": 10, "october": 10, "nov": 11, "november": 11, "dec": 12, "december": 12,
}

def calendar_url(start: date) -> str:
    return BASE_URL + "/en/tournament-calendar/world-tennis-tour-juniors-calendar/" + f"?categories=All&startdate={start.isoformat()}"

def category_from_url(url: str) -> str:
    m = re.search(r"/(j\d+)[-/]", url.lower())
    return m.group(1).upper() if m else ""

def clean_tournament_url(url: str) -> str:
    url = url.split("#")[0]
    for suffix in ["/acceptance-list/", "/draws-and-results/", "/fact-sheet/", "/order-of-play/", "/media-and-resources/"]:
        if suffix in url:
            url = url.split(suffix)[0] + "/"
    return url.rstrip("/") + "/"

def acceptance_url(url: str) -> str:
    return clean_tournament_url(url).rstrip("/") + "/acceptance-list/"

def parse_itf_date_range(text: str, default_year: int) -> tuple[str, str]:
    clean = re.sub(r"\s+", " ", text.strip())
    m = re.match(
        r"(?P<sd>\d{1,2})(?:\s+(?P<sm>[A-Za-z]+))?\s+to\s+"
        r"(?P<ed>\d{1,2})\s+(?P<em>[A-Za-z]+)\s+(?P<year>\d{4})",
        clean,
        flags=re.I,
    )
    if not m:
        return "", ""
    year = int(m.group("year") or default_year)
    end_month = MONTHS.get(m.group("em").lower())
    start_month_raw = m.group("sm")
    start_month = MONTHS.get(start_month_raw.lower()) if start_month_raw else end_month
    if not start_month or not end_month:
        return "", ""
    start_year = year - 1 if start_month > end_month else year
    try:
        return date(start_year, start_month, int(m.group("sd"))).isoformat(), date(year, end_month, int(m.group("ed"))).isoformat()
    except ValueError:
        return "", ""

def fetch_calendar_html(start: date, debug_dir: Path) -> str:
    url = calendar_url(start)
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto(url, wait_until="domcontentloaded", timeout=30000)
        page.wait_for_timeout(7000)
        html = page.content()
        browser.close()
    debug_dir.mkdir(parents=True, exist_ok=True)
    (debug_dir / "calendar_url.txt").write_text(url, encoding="utf-8")
    (debug_dir / "calendar.html").write_text(html, encoding="utf-8")
    return html

def parse_tournaments(html: str, debug_dir: Path, default_year: int) -> list[Tournament]:
    soup = BeautifulSoup(html, "lxml")
    tournaments = []
    seen = set()
    for row in soup.select("tr.whatson-table__tournament"):
        link = row.select_one("td.name a[href]")
        if not link:
            continue
        full_url = clean_tournament_url(urljoin(BASE_URL, link["href"]))
        if "/en/tournament/" not in full_url:
            continue
        category = category_from_url(full_url)
        if not category:
            continue
        date_cell = row.select_one("td.date span.date")
        date_text = date_cell.get_text(" ", strip=True) if date_cell else ""
        start_date, end_date = parse_itf_date_range(date_text, default_year)
        short = row.select_one("td.name .short")
        long_name = row.select_one("td.name .long")
        name = short.get_text(" ", strip=True) if short else link.get_text(" ", strip=True)
        if long_name:
            long_txt = long_name.get_text(" ", strip=True)
            if long_txt and long_txt not in name:
                name = f"{name} {long_txt}".strip()
        key = f"{full_url}|{start_date}|{end_date}"
        if key in seen:
            continue
        seen.add(key)
        tournaments.append(Tournament(
            name=name, url=full_url, acceptance_url=acceptance_url(full_url),
            category=category, date_text=date_text, start_date=start_date, end_date=end_date
        ))
    debug_dir.mkdir(parents=True, exist_ok=True)
    (debug_dir / "tournament_urls_all_month.txt").write_text(
        "\n".join(f"{t.category}\t{t.start_date}\t{t.end_date}\t{t.date_text}\t{t.name}\t{t.acceptance_url}" for t in tournaments),
        encoding="utf-8",
    )
    return tournaments

def get_tournaments(start: date, debug_dir: Path) -> list[Tournament]:
    return parse_tournaments(fetch_calendar_html(start, debug_dir), debug_dir, default_year=start.year)
