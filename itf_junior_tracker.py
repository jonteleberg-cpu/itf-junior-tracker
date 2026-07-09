#!/usr/bin/env python3
"""ITF World Tennis Tour Juniors – Swedish entry tracker.

Creates a Markdown report for Swedish players in next week's ITF junior entry lists.
Designed for GitHub Actions, but also works locally.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import sys
import time
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Iterable
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

BASE = "https://www.itftennis.com"
CALENDAR = BASE + "/en/tournament-calendar/world-tennis-tour-juniors-calendar/"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome Safari",
    "Accept-Language": "en-US,en;q=0.9,sv;q=0.8",
}
DRAW_SHORT = {"Main Draw": "M", "Qualifying": "Q", "Alternates": "Alt"}
DRAW_RANK = {"Main Draw": 0, "Qualifying": 1, "Alternates": 2}


@dataclass(frozen=True)
class Tournament:
    name: str
    category: str
    start_date: dt.date | None
    end_date: dt.date | None
    url: str
    acceptance_url: str


@dataclass
class Entry:
    player: str
    nation: str
    tournament: str
    category: str
    gender: str
    draw: str
    ranking: int | None
    wtn: float | None
    position: str
    info: str
    acceptance_url: str


def get(url: str, retries: int = 3, sleep: float = 0.8) -> str:
    last_error: Exception | None = None
    for i in range(retries):
        try:
            r = requests.get(url, headers=HEADERS, timeout=35)
            if r.status_code == 404:
                return ""
            r.raise_for_status()
            return r.text
        except Exception as e:  # noqa: BLE001
            last_error = e
            time.sleep(sleep * (i + 1))
    raise RuntimeError(f"Could not fetch {url}: {last_error}")


def parse_date(value: str | None) -> dt.date | None:
    if not value:
        return None
    value = value.strip()
    for fmt in ("%Y-%m-%d", "%d %b %Y", "%d %B %Y", "%m/%d/%Y %I:%M:%S %p"):
        try:
            return dt.datetime.strptime(value[: len(dt.datetime.now().strftime(fmt))], fmt).date()
        except Exception:
            pass
    m = re.search(r"(\d{1,2})\s+([A-Z][a-z]{2,8})\s*,?\s+(20\d{2})", value)
    if m:
        for fmt in ("%d %b %Y", "%d %B %Y"):
            try:
                return dt.datetime.strptime(" ".join(m.groups()), fmt).date()
            except Exception:
                pass
    return None


def int_or_none(text: str | None) -> int | None:
    if not text:
        return None
    m = re.search(r"\d+", text.replace(",", ""))
    return int(m.group()) if m else None


def float_or_none(text: str | None) -> float | None:
    if not text:
        return None
    try:
        return float(re.search(r"\d+(?:\.\d+)?", text).group())  # type: ignore[union-attr]
    except Exception:
        return None


def clean(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


def category_sort_key(category: str) -> int:
    m = re.search(r"J(\d+)", category or "")
    return -int(m.group(1)) if m else 9999


def week_range(selector: str) -> tuple[dt.date, dt.date]:
    today = dt.date.today()
    if selector == "this":
        monday = today - dt.timedelta(days=today.weekday())
    elif selector == "next":
        monday = today - dt.timedelta(days=today.weekday()) + dt.timedelta(days=7)
    else:
        d = dt.date.fromisoformat(selector)
        monday = d - dt.timedelta(days=d.weekday())
    return monday, monday + dt.timedelta(days=6)


def tournament_months(start: dt.date, end: dt.date) -> list[str]:
    months: list[str] = []
    cur = dt.date(start.year, start.month, 1)
    last = dt.date(end.year, end.month, 1)
    while cur <= last:
        months.append(cur.strftime("%Y-%m"))
        if cur.month == 12:
            cur = dt.date(cur.year + 1, 1, 1)
        else:
            cur = dt.date(cur.year, cur.month + 1, 1)
    return months


def parse_tournament_from_page(url: str, html: str) -> Tournament | None:
    if not html:
        return None
    soup = BeautifulSoup(html, "html.parser")
    h1 = soup.select_one("#ga__tournament-name, h1")
    name = clean(h1.get_text(" ")) if h1 else ""
    category = ""
    m = re.search(r"var\s+tournamentCategory\s*=\s*['\"]([^'\"]+)", html)
    if m:
        category = m.group(1)
    else:
        cm = re.search(r"\bJ(?:500|300|200|100|60|30)\b", name)
        category = cm.group(0) if cm else ""

    start_date = end_date = None
    for tag in soup.select('script[type="application/ld+json"]'):
        try:
            data = json.loads(tag.string or "{}")
        except Exception:
            continue
        if isinstance(data, dict) and data.get("@type") == "Event":
            start_date = parse_date(str(data.get("startDate", "")))
            end_date = parse_date(str(data.get("endDate", "")))
            name = name or clean(str(data.get("name", "")))
            break
    acceptance_url = url.rstrip("/") + "/acceptance-list/"
    return Tournament(name=name, category=category, start_date=start_date, end_date=end_date, url=url, acceptance_url=acceptance_url)


def discover_tournament_urls(start: dt.date, end: dt.date) -> list[str]:
    found: set[str] = set()
    for month in tournament_months(start, end):
        html = get(f"{CALENDAR}?categories=All&startdate={month}")
        # Rendered pages and saved pages both contain tournament links.
        for href in re.findall(r'href=["\']([^"\']*/en/tournament/[^"\']+?/[^"\']+?/20\d{2}/[^"\']+?)["\']', html):
            if "/acceptance-list" in href:
                href = href.split("/acceptance-list", 1)[0]
            found.add(urljoin(BASE, href).split("#")[0].rstrip("/"))
        for href in re.findall(r'"url"\s*:\s*"([^"]*/en/tournament/[^"]+)"', html):
            found.add(urljoin(BASE, href).split("#")[0].rstrip("/"))
    return sorted(found)


def discover_tournaments(start: dt.date, end: dt.date) -> list[Tournament]:
    tournaments: list[Tournament] = []
    for url in discover_tournament_urls(start, end):
        html = get(url)
        t = parse_tournament_from_page(url, html)
        if not t or not t.start_date:
            continue
        if start <= t.start_date <= end:
            tournaments.append(t)
    return sorted(tournaments, key=lambda t: (category_sort_key(t.category), t.name))


def infer_gender(html_before_block: str) -> str:
    hits = [(m.start(), m.group(1).title()) for m in re.finditer(r"\b(Boys|Girls)\b", html_before_block, re.I)]
    return hits[-1][1] if hits else ""


def parse_rows_from_table(table, tournament: Tournament, gender: str, draw: str, country: str) -> list[Entry]:
    entries: list[Entry] = []
    for tr in table.select("tbody tr"):
        cells = tr.find_all("td")
        if len(cells) < 2:
            continue
        nat = clean(cells[1].select_one(".acceptance-list__nationality").get_text(" ") if cells[1].select_one(".acceptance-list__nationality") else "")
        if country.upper() not in nat.upper().split():
            # Some RUS/BLR rows show flags without text, so require explicit country for Sweden.
            continue
        player_link = cells[1].select_one("a.acceptance-list__player") or cells[1].select_one("a")
        if not player_link:
            continue
        spans = player_link.find_all("span")
        player = clean(spans[-1].get_text(" ") if spans else player_link.get_text(" "))
        position = clean(cells[0].get_text(" "))
        ranking = None
        wtn = None
        if len(cells) > 2:
            ranking = int_or_none(cells[2].get_text(" "))
        if len(cells) > 3:
            wtn = float_or_none(cells[3].get_text(" "))
        info = clean(cells[-1].get_text(" ")) if len(cells) >= 5 else ""
        entries.append(Entry(player, country.upper(), tournament.name, tournament.category, gender, draw, ranking, wtn, position, info, tournament.acceptance_url))
    return entries


def parse_acceptance_list(tournament: Tournament, country: str = "SWE") -> list[Entry]:
    html = get(tournament.acceptance_url)
    if not html:
        return []
    soup = BeautifulSoup(html, "html.parser")
    entries: list[Entry] = []

    # Split by acceptance-list detail blocks to retain nearest Boys/Girls context.
    raw_blocks = re.split(r'(<div class="acceptance-lists__details">)', html)
    block_htmls: list[tuple[str, str]] = []
    prefix = raw_blocks[0] if raw_blocks else ""
    for i in range(1, len(raw_blocks), 2):
        block = raw_blocks[i] + (raw_blocks[i + 1] if i + 1 < len(raw_blocks) else "")
        block_htmls.append((prefix, block))
        prefix += block

    if block_htmls:
        for before, block in block_htmls:
            bs = BeautifulSoup(block, "html.parser")
            h3 = bs.find("h3")
            draw = clean(h3.get_text(" ")) if h3 else ""
            draw = {"MAIN DRAW": "Main Draw", "QUALIFYING": "Qualifying", "ALTERNATES": "Alternates"}.get(draw.upper(), draw)
            gender = infer_gender(before[-5000:])
            table = bs.select_one("table.acceptance-list")
            if table and draw:
                entries.extend(parse_rows_from_table(table, tournament, gender, draw, country))
    else:
        for table in soup.select("table.acceptance-list"):
            h3 = table.find_previous("h3")
            draw = clean(h3.get_text(" ")) if h3 else ""
            draw = {"MAIN DRAW": "Main Draw", "QUALIFYING": "Qualifying", "ALTERNATES": "Alternates"}.get(draw.upper(), draw)
            entries.extend(parse_rows_from_table(table, tournament, "", draw, country))

    # One row per player/tournament: keep best list status M > Q > Alt.
    best: dict[tuple[str, str, str], Entry] = {}
    for e in entries:
        key = (e.player.lower(), e.acceptance_url, e.gender)
        if key not in best or DRAW_RANK.get(e.draw, 99) < DRAW_RANK.get(best[key].draw, 99):
            best[key] = e
    return list(best.values())


def format_rank(r: int | None) -> str:
    return str(r) if r is not None else "NR"


def format_entry(e: Entry) -> str:
    short = DRAW_SHORT.get(e.draw, e.draw)
    return f"- {e.player} ({format_rank(e.ranking)}) – {short} #{e.position}"


def make_markdown(entries: list[Entry], start: dt.date, end: dt.date, scanned: int, errors: list[str]) -> str:
    lines = [f"# Svenska ITF-juniorer – {start.isoformat()} till {end.isoformat()}", ""]
    if not entries:
        lines += ["Inga svenska spelare hittades i publicerade acceptance lists för perioden.", ""]
    grouped: dict[tuple[str, str, str, str], list[Entry]] = {}
    for e in sorted(entries, key=lambda x: (category_sort_key(x.category), x.tournament, x.gender, DRAW_RANK.get(x.draw, 9), int_or_none(x.position) or 9999, x.player)):
        grouped.setdefault((e.category, e.tournament, e.gender or "Okänt", e.acceptance_url), []).append(e)
    for (category, tournament, gender, url), rows in grouped.items():
        title = clean(re.sub(rf"^{re.escape(category)}\s+", "", tournament, flags=re.I))
        title = re.sub(rf"\b{re.escape(category)}\b", "", title).strip()
        lines.append(f"## [{category} {title} – {gender}]({url})")
        for e in rows:
            lines.append(format_entry(e))
        lines.append("")
    lines += ["---", f"Skannade turneringar: {scanned}"]
    if errors:
        lines.append(f"Varningar: {len(errors)}")
        for err in errors[:20]:
            lines.append(f"- {err}")
    return "\n".join(lines).rstrip() + "\n"


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--week", default="next", help="next, this, or date YYYY-MM-DD")
    p.add_argument("--country", default="SWE")
    p.add_argument("--out", default="reports/next_week.md")
    p.add_argument("--json", default="reports/swedish_entries.json")
    args = p.parse_args(argv)

    start, end = week_range(args.week)
    errors: list[str] = []
    tournaments = discover_tournaments(start, end)
    entries: list[Entry] = []
    for t in tournaments:
        try:
            entries.extend(parse_acceptance_list(t, args.country))
        except Exception as e:  # noqa: BLE001
            errors.append(f"{t.name}: {e}")

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(make_markdown(entries, start, end, len(tournaments), errors), encoding="utf-8")

    jout = Path(args.json)
    jout.parent.mkdir(parents=True, exist_ok=True)
    jout.write_text(json.dumps([asdict(e) for e in entries], ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"Wrote {out} with {len(entries)} Swedish entries from {len(tournaments)} tournaments")
    return 0 if not errors else 2


if __name__ == "__main__":
    raise SystemExit(main())
