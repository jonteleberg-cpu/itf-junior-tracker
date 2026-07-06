from __future__ import annotations
import argparse
from datetime import date, timedelta
from pathlib import Path
from playwright.sync_api import sync_playwright
from . import __version__
from .acceptance import get_entries
from .calendar import get_tournaments
from .report import print_report, save_excel, save_json

def monday(d: date) -> date:
    return d - timedelta(days=d.weekday())

def resolve_range(week: str) -> tuple[date, date]:
    base = monday(date.today())
    if week == "current":
        return base, base + timedelta(days=6)
    return base + timedelta(days=7), base + timedelta(days=13)

def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--week", choices=["current", "next"], default="next")
    parser.add_argument("--nation", default="SWE")
    parser.add_argument("--limit", type=int, default=0)
    args = parser.parse_args()

    data_dir = Path("data")
    debug_dir = data_dir / "debug"
    debug_dir.mkdir(parents=True, exist_ok=True)
    start, end = resolve_range(args.week)

    print(f"ITF Junior Tracker v{__version__}")
    print(f"Period: {start} till {end}")
    print("Hämtar kalender...")

    tournaments = get_tournaments(start=start, debug_dir=debug_dir)
    if args.limit:
        tournaments = tournaments[:args.limit]

    print()
    print("Turneringar som hittades:")
    print("-" * 40)
    for t in tournaments:
        print(f"{t.category:5} {t.name}")
        print(f"      {t.acceptance_url}")

    all_entries, errors = [], []
    print()
    print(f"Läser {len(tournaments)} acceptance lists med snabb Playwright...")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        for i, tournament in enumerate(tournaments, 1):
            try:
                entries = get_entries(page, tournament, debug_dir=debug_dir, index=i, nation=args.nation)
                print(f"[{i}/{len(tournaments)}] {tournament.name}: {len(entries)} {args.nation}")
                all_entries.extend(entries)
            except Exception as exc:
                msg = f"[{i}/{len(tournaments)}] {tournament.name}: FEL {exc}"
                print(msg)
                errors.append(msg)
        browser.close()

    save_json(all_entries, data_dir / "swedish_entries.json")
    save_excel(all_entries, data_dir / "swedish_entries.xlsx")
    (debug_dir / "run_summary.txt").write_text("\n".join([
        f"ITF Junior Tracker v{__version__}",
        f"Period: {start} till {end}",
        f"Tournaments: {len(tournaments)}",
        f"Entries found: {len(all_entries)}",
        f"Errors: {len(errors)}",
        "",
        "Errors:",
        *errors,
    ]), encoding="utf-8")

    print_report(all_entries)
    print()
    print("Sparat:")
    print("data/swedish_entries.json")
    print("data/swedish_entries.xlsx")
    print("data/debug/run_summary.txt")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
