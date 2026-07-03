from datetime import date, timedelta


def monday(d: date) -> date:
    return d - timedelta(days=d.weekday())


def resolve_range(week: str, start: str | None, end: str | None):
    if start and end:
        return date.fromisoformat(start), date.fromisoformat(end)

    today = date.today()
    base = monday(today)

    if week == "current":
        return base, base + timedelta(days=6)

    return base + timedelta(days=7), base + timedelta(days=13)
