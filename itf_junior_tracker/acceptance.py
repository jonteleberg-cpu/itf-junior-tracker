from __future__ import annotations

import re
from pathlib import Path
from typing import Optional

import requests
from bs4 import BeautifulSoup

from .models import Entry, Tournament

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126 Safari/537.36"
    )
}


def safe_name(value: str) -> str:
    value = re.sub(r"[^A-Za-z0-9ÅÄÖåäö_-]+", "_", value.strip())
    return value[:80] or "unknown"


def to_int(value: str) -> Optional[int]:
    value = value.strip().replace(",", "")
    return int(value) if value.isdigit() else None


def to_float(value: str) -> Optional[float]:
    try:
        return float(value.strip())
    except ValueError:
        return None


def fetch_html(url: str) -> str:
    r = requests.get(url, headers=HEADERS, timeout=30)
    r.raise_for_status()
    return r.text


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
            if not nationality:
                continue

            if nationality.get_text(" ", strip=True).upper() != nation:
                continue

            player_link = row.select_one("a.acceptance-list__player")
            if not player_link:
                continue

            spans = player_link.find_all("span")
            player = spans[-1].get_text(" ", strip=True) if spans else player_link.get_text(" ", strip=True)

            cells = [c.get_text(" ", strip=True) for c in row.find_all("td")]

            position = cells[0] if len(cells) > 0 else ""
            ranking = to_int(cells[2]) if len(cells) > 2 else None
            wtn = to_float(cells[3]) if len(cells) > 3 else None
            info = cells[-1] if cells else ""

            entries.append(
                Entry(
                    player=player,
                    nation=nation,
                    tournament=tournament.name,
                    category=tournament.category,
                    draw=draw,
                    ranking=ranking,
                    wtn=wtn,
                    position=position,
                    info=info,
                    acceptance_url=tournament.acceptance_url,
                )
            )

    return entries


def get_entries(
    tournament: Tournament,
    nation: str = "SWE",
    debug_dir: str | Path | None = None,
    debug_index: int | None = None,
) -> list[Entry]:
    html = fetch_html(tournament.acceptance_url)

    if debug_dir and debug_index is not None and debug_index <= 20:
        debug = Path(debug_dir)
        debug.mkdir(parents=True, exist_ok=True)
        filename = f"{debug_index:03d}_{safe_name(tournament.category)}_{safe_name(tournament.name)}.html"
        (debug / filename).write_text(html, encoding="utf-8")

    return parse_entries(html, tournament, nation=nation)
