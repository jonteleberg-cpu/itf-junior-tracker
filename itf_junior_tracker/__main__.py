from __future__ import annotations

import argparse
from pathlib import Path

from .acceptance import get_entries
from .calendar import get_tournaments
from .dates import resolve_range
from .report import print_report, save_excel, save_json


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--week", choices=["current", "next"], default="next")
    parser.add_argument("--start")
    parser.add_argument("--end")
    parser.add_argument("--nation", default="SWE")
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--headful", action="store_true")
    args = parser.parse_args()

    debug_dir = Path("data") / "debug"
    debug_dir.mkdir(parents=True, exist_ok=True)

    start, end = resolve_range(args.week, args.start, args.end)

    print(f"Period: {start} till {end}")
    print("Hämtar kalender...")

    tournaments = get_tournaments(headless=not args.headful, debug_dir=debug_dir)

    if args.limit:
        tournaments = tournaments[: args.limit]

    print()
    print("Turneringar som hittades:")
    print("-" * 40)
    for t in tournaments:
        print(f"{t.category:5} {t.name}")
        print(f"      {t.acceptance_url}")

    print()
    print(f"Hittade {len(tournaments)} möjliga turneringar.")
    print("Läser acceptance lists...")

    all_entries = []

    for i, t in enumerate(tournaments, 1):
        print()
        print(f"[{i}/{len(tournaments)}] Öppnar {t.name}")
        print(f"  {t.acceptance_url}")

        try:
            entries = get_entries(t, nation=args.nation, debug_dir=debug_dir, debug_index=i)
            print(f"  {len(entries)} svenska spelare")
            if entries:
                all_entries.extend(entries)
        except Exception as exc:
            print(f"  FEL: {exc}")

    save_json(all_entries, Path("data") / "swedish_entries.json")
    save_excel(all_entries, Path("data") / "swedish_entries.xlsx")
    print_report(all_entries)

    print()
    print("Sparat:")
    print("data/swedish_entries.json")
    print("data/swedish_entries.xlsx")
    print("data/debug/")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
