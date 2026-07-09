from __future__ import annotations

import argparse
import json
import re
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from urllib.parse import urljoin

from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError


BASE_URL = "https://www.itftennis.com"


ROUND_PATTERNS = [
    ("Winner", ["winner", "champion"]),
    ("Final", ["final"]),
    ("Semifinal", ["semi-final", "semifinal", "sf"]),
    ("Kvartsfinal", ["quarter-final", "quarterfinal", "qf"]),
    ("R16", ["round of 16", "r16"]),
    ("R32", ["round of 32", "r32"]),
    ("R64", ["round of 64", "r64"]),
    ("Kval", ["qualifying", "qualifier"]),
]


def latest_snapshot(history_dir: Path) -> Path:
    files = sorted(history_dir.glob("*_entries.json"))
    if not files:
        raise FileNotFoundError("No entry snapshots found in data/history/")
    return files[-1]


def draws_url_from_acceptance(url: str) -> str:
    return url.replace("/acceptance-list/", "/draws-and-results/")


def safe_filename(value: str) -> str:
    value = re.sub(r"[^A-Za-z0-9ÅÄÖåäö_-]+", "_", value.strip())
    return value[:100] or "unknown"


def load_entries(path: Path) -> list[dict]:
    return json.loads(path.read_text(encoding="utf-8"))


def tournament_key(entry: dict) -> tuple[str, str, str, str]:
    return (
        entry.get("category", ""),
        entry.get("tournament", ""),
        entry.get("gender", ""),
        entry.get("acceptance_url", ""),
    )


def fetch_draws_html(page, url: str) -> tuple[str, str]:
    page.goto(url, wait_until="domcontentloaded", timeout=20000)
    status = "domcontentloaded"
    try:
        page.wait_for_selector("body", timeout=5000)
    except PlaywrightTimeoutError:
        status = "body-timeout"
    page.wait_for_timeout(5000)
    return page.content(), status


def html_to_text(html: str) -> str:
    soup = BeautifulSoup(html, "lxml")
    return soup.get_text("\n", strip=True)


def infer_round_for_player(text: str, player: str) -> str:
    low = text.lower()
    name = player.lower()

    if name not in low:
        return "Ej hittad"

    idx = low.find(name)
    window = low[max(0, idx - 3000): idx + 3000]

    best = "Hittad"
    for label, patterns in ROUND_PATTERNS:
        if any(p in window for p in patterns):
            best = label
            break

    return best


def make_report(snapshot_path: Path, entries: list[dict], result_rows: list[dict]) -> str:
    period = snapshot_path.name.split("_entries.json")[0]
    lines = []
    lines.append("# ITF Junior Tracker – resultat")
    lines.append("")
    lines.append(f"**Entry-snapshot:** `{snapshot_path.name}`")
    lines.append(f"**Skapad:** {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}")
    lines.append("")
    lines.append("> Första resultatversion. Poäng beräknas inte ännu – först verifierar vi hur ITF:s resultat-HTML ser ut.")
    lines.append("")

    grouped = defaultdict(list)
    for row in result_rows:
        header = f"{row['category']} {row['tournament']} - {row['gender']}"
        grouped[header].append(row)

    for header, rows in grouped.items():
        url = rows[0].get("draws_url", "")
        lines.append(f"## [{header}]({url})")
        lines.append("")
        for r in rows:
            lines.append(f"- {r['player']} — {r['round']} — poäng: TBD")
        lines.append("")

    lines.append("---")
    lines.append(f"Turneringar: {len(grouped)}")
    lines.append(f"Svenska entries kontrollerade: {len(result_rows)}")
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--snapshot", help="Path to *_entries.json snapshot")
    args = parser.parse_args()

    data_dir = Path("data")
    history_dir = data_dir / "history"
    results_dir = data_dir / "results"
    debug_dir = results_dir / "debug"
    debug_dir.mkdir(parents=True, exist_ok=True)

    snapshot_path = Path(args.snapshot) if args.snapshot else latest_snapshot(history_dir)
    entries = load_entries(snapshot_path)

    tournaments = {}
    for e in entries:
        tournaments.setdefault(tournament_key(e), []).append(e)

    result_rows = []

    print(f"ITF Junior Tracker results alpha")
    print(f"Snapshot: {snapshot_path}")
    print(f"Tournaments: {len(tournaments)}")
    print(f"Entries: {len(entries)}")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        for i, ((category, tournament, gender, acceptance_url), rows) in enumerate(tournaments.items(), 1):
            draws_url = draws_url_from_acceptance(acceptance_url)
            print(f"[{i}/{len(tournaments)}] {category} {tournament} - {gender}")

            try:
                html, status = fetch_draws_html(page, draws_url)
            except Exception as exc:
                html, status = "", f"ERROR: {exc}"

            base = f"{i:03d}_{safe_filename(category)}_{safe_filename(tournament)}_{safe_filename(gender)}"
            if html:
                (debug_dir / f"{base}.html").write_text(html, encoding="utf-8")
                text = html_to_text(html)
                (debug_dir / f"{base}.txt").write_text(text, encoding="utf-8")
            else:
                text = ""

            for e in rows:
                result_rows.append({
                    "category": category,
                    "tournament": tournament,
                    "gender": gender,
                    "player": e.get("player", ""),
                    "ranking": e.get("ranking"),
                    "draws_url": draws_url,
                    "round": infer_round_for_player(text, e.get("player", "")) if text else "Fel vid hämtning",
                    "status": status,
                })

        browser.close()

    report = make_report(snapshot_path, entries, result_rows)
    (results_dir / "results_report.md").write_text(report, encoding="utf-8")
    (results_dir / "results_rows.json").write_text(
        json.dumps(result_rows, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print("Sparat:")
    print("data/results/results_report.md")
    print("data/results/results_rows.json")
    print("data/results/debug/")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
