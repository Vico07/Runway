"""Calendar-month comparisons of the existing daily forecast, without rebuilding its money model."""
from __future__ import annotations

from . import forecast


def months(fc: dict, account_id: str, selected: tuple[str, ...] = ("2026-11", "2026-12")) -> list[dict]:
    account = next((a for a in fc["accounts"] if a["id"] == account_id), None)
    if not account:
        return []
    out = []
    for month in selected:
        indices = [i for i, day in enumerate(fc["dates"]) if day.startswith(month)]
        if not indices:
            continue
        first, last = indices[0], indices[-1]
        events = [e for e in fc["events"] if e["account_id"] == account_id and e["date"].startswith(month)]
        income = round(sum(e["amount"] for e in events if e["amount"] > 0), 2)
        expenses = round(-sum(e["amount"] for e in events if e["amount"] < 0)
                         + sum(v for d, v in account["spend"].items() if d.startswith(month)), 2)
        opening = account["series"][first - 1] if first else account["balance"]
        series = account["series"][first:last + 1]
        dates = fc["dates"][first:last + 1]
        out.append({"month": month, "opening": opening, "closing": series[-1], "income": income,
                    "expenses": expenses, "net": round(income - expenses, 2), "low": forecast.low(series, dates),
                    "days": [{"date": d, "balance": b} for d, b in zip(dates, series, strict=True)]})
    return out
