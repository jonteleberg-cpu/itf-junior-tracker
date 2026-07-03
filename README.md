# ITF Junior Tracker

Datainsamlare för svenska spelare på ITF World Tennis Tour Juniors.

## Körning via GitHub Actions

Workflow finns i `.github/workflows/weekly.yml`.

Den kan köras manuellt via:
**Actions → Weekly ITF Junior Tracker → Run workflow**

Resultat skapas som artifacts:
- `swedish_entries.json`
- `swedish_entries.xlsx`

## Kör lokalt om Python finns

```bash
pip install -r requirements.txt
playwright install chromium
python -m itf_junior_tracker --week next
```

## Status

Första versionen fokuserar på entries/acceptance lists.
