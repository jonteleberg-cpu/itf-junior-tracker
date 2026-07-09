from __future__ import annotations
import json
import re
from datetime import date
from pathlib import Path
import pandas as pd
from .models import Entry

CATEGORY_ORDER = {"J500": 0, "J300": 1, "J200": 2, "J100": 3, "J60": 4, "J30": 5}
DRAW_LABEL = {"Main Draw": "M", "Qualifying": "Q", "Alternates": "Alt", "Alternate": "Alt"}
DRAW_ORDER = {"M": 0, "Q": 1, "Alt": 2}
GENDER_ORDER = {"Girls": 0, "Boys": 1, "": 2}
SWEDISH_MONTHS = {1:"januari",2:"februari",3:"mars",4:"april",5:"maj",6:"juni",7:"juli",8:"augusti",9:"september",10:"oktober",11:"november",12:"december"}

def date_sv(value: date) -> str:
    return f"{value.day} {SWEDISH_MONTHS[value.month]} {value.year}"

def clean_tournament_name(name: str, category: str) -> str:
    text = re.sub(r"\s+", " ", name).strip()
    text = re.sub(r"\([A-Z]{3}\)", "", text).strip()
    if category:
        text = re.sub(rf"\b{re.escape(category)}\b", "", text, flags=re.I)
    text = re.sub(r"\s+", " ", text).strip()
    parts = text.split()
    if len(parts) % 2 == 0:
        half = len(parts)//2
        if [p.lower() for p in parts[:half]] == [p.lower() for p in parts[half:]]:
            parts = parts[:half]
    return " ".join(parts).title()

def draw_short(draw: str) -> str:
    return DRAW_LABEL.get(draw, draw)

def pos_int(value: str) -> int:
    try:
        return int(str(value).replace("#", "").strip())
    except ValueError:
        return 999999

def entry_sort_key(e: Entry):
    return (CATEGORY_ORDER.get(e.category,99), clean_tournament_name(e.tournament,e.category), GENDER_ORDER.get(e.gender,9), DRAW_ORDER.get(draw_short(e.draw),9), pos_int(e.position), e.player)

def grouped_entries(entries: list[Entry]):
    entries = sorted(entries, key=entry_sort_key)
    grouped = {}; urls = {}
    for e in entries:
        tournament_name = clean_tournament_name(e.tournament, e.category)
        header = f"{e.category} {tournament_name} - {e.gender or 'Unknown'}"
        grouped.setdefault(header, []).append(e)
        urls.setdefault(header, e.acceptance_url)
    return grouped, urls

def make_weekly_report(entries: list[Entry], start: date, end: date, markdown: bool = False) -> str:
    lines = []
    if markdown:
        lines += ["# ITF Junior Tracker", "", f"**Period:** {date_sv(start)} – {date_sv(end)}", ""]
    else:
        lines += ["="*56, "ITF Junior Tracker", f"Period: {date_sv(start)} – {date_sv(end)}", "="*56, ""]
    if not entries:
        lines.append("Inga svenska spelare hittades.")
        return "\n".join(lines)+"\n"
    grouped, urls = grouped_entries(entries)
    for header, rows in grouped.items():
        if markdown:
            lines.append(f"## [{header}]({urls[header]})")
            lines.append("")
            for e in rows:
                ranking = f" ({e.ranking})" if e.ranking else ""
                list_code = draw_short(e.draw); pos = f"#{e.position}" if e.position else ""
                name = f"[{e.player}]({e.player_url})" if e.player_url else e.player
                lines.append(f"- {name}{ranking}    {list_code:<3}  {pos}")
            lines.append("")
        else:
            lines.append(header); lines.append("-"*len(header))
            for e in rows:
                ranking = f" ({e.ranking})" if e.ranking else ""
                list_code = draw_short(e.draw); pos = f"#{e.position}" if e.position else ""
                lines.append(f"{e.player}{ranking}    {list_code:<3}  {pos}")
            lines.append("")
    if markdown:
        lines += ["---", f"**Turneringar med svenska spelare:** {len(grouped)}", f"**Svenska entries:** {len(entries)}"]
    else:
        lines += ["-"*56, f"Turneringar med svenska spelare: {len(grouped)}", f"Svenska entries: {len(entries)}"]
    return "\n".join(lines)+"\n"

def print_report(entries: list[Entry], start: date, end: date) -> None:
    print(); print(make_weekly_report(entries,start,end,markdown=False))

def save_weekly_report(entries: list[Entry], start: date, end: date, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True); path.write_text(make_weekly_report(entries,start,end,markdown=False), encoding="utf-8")

def save_weekly_report_md(entries: list[Entry], start: date, end: date, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True); path.write_text(make_weekly_report(entries,start,end,markdown=True), encoding="utf-8")

def save_json(entries: list[Entry], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True); path.write_text(json.dumps([e.to_dict() for e in sorted(entries,key=entry_sort_key)], ensure_ascii=False, indent=2), encoding="utf-8")

def save_excel(entries: list[Entry], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    rows=[]
    for e in sorted(entries,key=entry_sort_key):
        rows.append({"Category":e.category,"Tournament":clean_tournament_name(e.tournament,e.category),"Gender":e.gender,"Player":e.player,"Ranking":e.ranking,"List":draw_short(e.draw),"Position":pos_int(e.position) if e.position else "","WTN":e.wtn,"Start":e.tournament_start,"End":e.tournament_end,"Tournament URL":e.acceptance_url,"Player URL":e.player_url})
    df=pd.DataFrame(rows)
    if df.empty:
        df=pd.DataFrame(columns=["Category","Tournament","Gender","Player","Ranking","List","Position","WTN","Start","End","Tournament URL","Player URL"])
    df.to_excel(path,index=False)
