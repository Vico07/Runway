"""Small, read-only Home Assistant summaries. No credentials, account numbers or transaction histories."""
from __future__ import annotations

from datetime import date, timedelta

from sqlalchemy import select

from ...domain import forecast
from ...storage import db
from ...storage.models import Account, Category
from ..contract import FamilyModuleReply
from .budget import api_budget


def summary(conn) -> dict:
    today = date.today()
    fc, _ = forecast.project(conn, today, 90)
    cash = [a for a in fc["accounts"] if a["kind"] == "checking"]
    income = set(conn.execute(select(Category.name).where(Category.is_income == 1, Category.name != "Refunds")).scalars())
    paychecks = [e for e in fc["events"] if e["amount"] > 0 and e.get("category") in income]
    payments = [e for e in fc["events"] if e["amount"] < 0][:5]
    balances = db.rows(conn.execute(select(Account.balance_date).where(Account.hidden == 0, Account.kind.in_(["checking", "credit", "savings"]))))
    stale = not balances or any(not a["balance_date"] or a["balance_date"][:10] < (today - timedelta(days=7)).isoformat() for a in balances)
    series = [round(sum(a["series"][i] for a in cash), 2) for i in range(len(fc["dates"]))] if cash else []
    low = forecast.low(series, fc["dates"])
    return {"as_of": today.isoformat(), "checking_balance": round(sum(a["balance"] for a in cash), 2) if cash else None,
            "minimum_forecast_balance": low["balance"] if low else None,
            "negative_forecast": bool(low and low["balance"] < 0), "stale": stale, "verified": False,
            "source": "User-entered or last recorded balances; not independently reconciled",
            "next_paycheck": {"date": paychecks[0]["date"], "expected_amount": paychecks[0]["amount"], "verified": False} if paychecks else None,
            "upcoming": [{"name": e["name"], "date": e["date"], "expected_amount": -e["amount"], "verified": False} for e in payments],
            "warnings": fc["warnings"], "coverage": "Only checking accounts included in Runway's forecast; confirm account coverage"}


def api_ha_summary(conn, _q, _b) -> FamilyModuleReply:
    return {"data": summary(conn)}


def api_ha_upcoming(conn, _q, _b) -> FamilyModuleReply:
    value = summary(conn)
    return {"data": {"next_paycheck": value["next_paycheck"], "payments": value["upcoming"], "verified": False}}


def api_ha_cashflow(conn, _q, _b) -> FamilyModuleReply:
    value = summary(conn)
    return {"data": {k: value[k] for k in ("as_of", "checking_balance", "minimum_forecast_balance", "negative_forecast", "warnings", "stale", "verified")}}


def api_ha_budget(conn, q, _b) -> FamilyModuleReply:
    budget = api_budget(conn, q, {})
    return {"data": {"month": date.today().strftime("%Y-%m"), "categories": [{k: r[k] for k in ("name", "budget", "spent", "left", "expected")} for r in budget["categories"] if not r["parent"]][:50],
                     "uncategorized": budget["uncategorized"], "verified": False}}
