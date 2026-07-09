# ITF junior tracker – Sweden

Kör nästa veckas svenska ITF-juniorlista:

```bash
pip install -r requirements.txt
python itf_junior_tracker.py --week next
```

Output:

- `reports/next_week.md` – färdig rapport med klickbara turneringsrubriker
- `reports/swedish_entries.json` – rådata

Formatet är sorterat J500 → J30 och visar:

`Spelare (ranking) – M/Q/Alt #position`

Exempel:

`Filip Hesser (352) – M #13`
