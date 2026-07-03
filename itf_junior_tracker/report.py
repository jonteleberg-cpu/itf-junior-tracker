from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from .models import Entry


def print_report(entries: list[Entry]) -> None:
    print()
    print("Svenska ITF-juniorer")
    print("=" * 40)

    if not entries:
        print("Inga svenska spelare hittades.")
        return

    grouped = {}
    for e in entries:
        grouped.setdefault(f"{e.category} {e.tournament}".strip(), []).append(e)

    for tournament, rows in grouped.items():
        print()
        print(tournament)
        print("-" * len(tournament))
        for e in sorted(rows, key=lambda x: (x.draw, x.ranking or 999999, x.player)):
            rank = f" ({e.ranking})" if e.ranking else ""
            draw = f" – {e.draw}" if e.draw else ""
            print(f"  {e.player}{rank}{draw}")


def save_json(entries: list[Entry], path: str | Path) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps([e.to_dict() for e in entries], ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def save_excel(entries: list[Entry], path: str | Path) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    df = pd.DataFrame([e.to_dict() for e in entries])
    if df.empty:
        df = pd.DataFrame(
            columns=[
                "player",
                "nation",
                "tournament",
                "category",
                "draw",
                "ranking",
                "wtn",
                "position",
                "info",
                "acceptance_url",
            ]
        )

    df.to_excel(path, index=False)
