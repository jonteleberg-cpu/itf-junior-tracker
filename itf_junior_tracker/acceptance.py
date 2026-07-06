from __future__ import annotations
import re
from pathlib import Path
from typing import Optional
from bs4 import BeautifulSoup
from playwright.sync_api import Page, TimeoutError as PlaywrightTimeoutError
from .models import Entry, Tournament

def safe_filename(value: str) -> str:
    value = re.sub(r"[^A-Za-z0-9ÅÄÖåäö_-]+", "_", value.strip())
    return value[:90] or "unknown"

def to_int(value: str) -> Optional[int]:
    value = value.strip().replace(",", "")
    return int(value) if value.isdigit() else None

def to_float(value: str) -> Optional[float]:
    try:
        return float(value.strip())
    except ValueError:
        return None

def fetch_rendered_html(page: Page, url: str) -> tuple[str, str]:
    page.goto(url, wait_until="domcontentloaded", timeout=15000)
    status = "domcontentloaded"
    try:
        page.wait_for_selector("table.acceptance-list", timeout=10000)
        status = "table-found"
    except PlaywrightTimeoutError:
        status = "table-timeout"
    page.wait_for_timeout(1000)
    return page.content(), status

def draw_for_table(table) -> str:
    h = table.find_previous("h3")
    return h.get_text(" ", strip=True).title() if h else ""

def parse_entries(html: str, tournament: Tournament, nation: str = "SWE") -> list[Entry]:
    soup = BeautifulSoup(html, "lxml")
    entries = []
    for table in soup.select("table.acceptance-list"):
        draw = draw_for_table(table)
        if draw.upper() == "WITHDRAWALS":
            continue
        for row in table.select("tbody tr"):
            nationality = row.select_one(".acceptance-list__nationality")
            if not nationality or nationality.get_text(" ", strip=True).upper() != nation:
                continue
            player_link = row.select_one("a.acceptance-list__player")
            if not player_link:
                continue
            spans = player_link.find_all("span")
            player = spans[-1].get_text(" ", strip=True) if spans else player_link.get_text(" ", strip=True)
            player = re.sub(r"\s+", " ", player).strip()
            cells = [c.get_text(" ", strip=True) for c in row.find_all("td")]
            entries.append(Entry(
                player=player,
                nation=nation,
                tournament=tournament.name,
                category=tournament.category,
                draw=draw,
                ranking=to_int(cells[2]) if len(cells) > 2 else None,
                wtn=to_float(cells[3]) if len(cells) > 3 else None,
                position=cells[0] if len(cells) > 0 else "",
                info=cells[-1] if cells else "",
                acceptance_url=tournament.acceptance_url,
            ))
    return entries

def get_entries(page: Page, tournament: Tournament, debug_dir: Path, index: int, nation: str = "SWE") -> list[Entry]:
    html, status = fetch_rendered_html(page, tournament.acceptance_url)
    debug_dir.mkdir(parents=True, exist_ok=True)
    if index <= 40:
        filename = f"{index:03d}_{safe_filename(tournament.category)}_{safe_filename(tournament.name)}_{status}.html"
        (debug_dir / filename).write_text(html, encoding="utf-8")
    entries = parse_entries(html, tournament, nation=nation)
    table_count = html.count('table class="acceptance-list')
    with (debug_dir / "acceptance_debug.txt").open("a", encoding="utf-8") as f:
        f.write(
            f"{index}\t{tournament.name}\tstatus={status}\t"
            f"acceptance-list={html.count('acceptance-list')}\t"
            f"table_count={table_count}\t"
            f"{nation}={html.upper().count(nation.upper())}\t"
            f"entries={len(entries)}\t{tournament.acceptance_url}\n"
        )
    return entries
