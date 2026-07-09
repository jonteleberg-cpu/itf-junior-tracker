v1.2 patch

Ny funktion:
- Sparar entry-snapshot automatiskt i `data/history/`.
- Snapshot sparas med startdatum, t.ex:
  - data/history/2026-07-13_entries.json
  - data/history/2026-07-13_weekly_report.md
  - data/history/2026-07-13_weekly_report.txt

Varför:
- Acceptance lists kan försvinna efter turneringsstart.
- Resultatdelen ska senare kunna utgå från sparad snapshot.
