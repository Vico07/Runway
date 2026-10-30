"""A household spending overview built from Runway's split-aware reporting and budget rows."""
from __future__ import annotations

import json
from collections import defaultdict
from datetime import date, timedelta

from sqlalchemy import func, select

from . import forecast, reports
from .. import dates
from ..storage import db
from ..storage.models import Account, Recurring, Transaction

CLASS_KEY = "family_spending_classes"
CLASSES = ("fixed", "variable", "principal", "interest", "transfer", "unallocated_debt")


def classes(conn) -> dict[str, str]:
    return json.loads(db.get_setting(conn, CLASS_KEY) or "{}")


def overview(conn, start: date, end: date, budget: dict, account: str = "", category: str = "", today: date | None = None) -> dict:
    today = today or date.today()
    kinds = reports._Kinds(conn)
    flags = classes(conn)
    accounts = db.rows(conn.execute(select(Account).order_by(Account.name)))
    rows = reports._rows(conn, dates.add_months(start, -3).isoformat(), end.isoformat())
    def fits(r):
        c = kinds.cats.get(r["category"])
        return (not account or r["account_id"] == account) and (not category or r["category"] == category or (c and category in c["path"]))
    rows = [r for r in rows if fits(r)]
    current = [r for r in rows if start.isoformat() <= r["posted"] < end.isoformat()]
    def kind(r):
        if not r["category"]:
            return "unclassified"
        base = kinds.kind(r)
        if base != "spend":
            return base
        c = kinds.cats.get(r["category"])
        inherited = next((flags[name] for name in reversed(c["path"]) if name in flags), None) if c else None
        return inherited or ("unallocated_debt" if kinds.top(r["category"]) in ("Mortgage", "Loans") else "variable")
    consumed = [r for r in current if kind(r) in ("fixed", "variable", "interest")]
    spent = round(-sum(r["amount"] for r in consumed), 2)
    groups: dict[str, float] = defaultdict(float)
    merchants: dict[str, float] = defaultdict(float)
    weeks: dict[str, float] = defaultdict(float)
    monthly: dict[str, float] = defaultdict(float)
    for r in rows:
        if kind(r) not in ("fixed", "variable", "interest"):
            continue
        monthly[r["month"]] -= r["amount"]
        if start.isoformat() <= r["posted"] < end.isoformat():
            groups[kinds.top(r["category"])] -= r["amount"]
            merchants[reports.merchant_name(r)] -= r["amount"]
            day = dates.parse_day(r["posted"])
            weeks[(day - timedelta(days=day.weekday())).isoformat()] -= r["amount"]
    days = (end - start).days
    elapsed = max(0, min(days, (today - start).days + 1))
    variable = -sum(r["amount"] for r in consumed if kind(r) == "variable")
    fixed = round(spent - variable, 2)
    # Scheduled future expenses come from the same forecast used by Budget. Pace is explicitly an estimate.
    remaining_fixed = sum(r["expected"] for r in budget["categories"] if not r["parent"] and flags.get(r["name"]) in ("fixed", "interest"))
    scheduled_variable = sum(r["expected"] for r in budget["categories"] if not r["parent"] and flags.get(r["name"], "variable") == "variable" and r["name"] not in ("Mortgage", "Loans"))
    pace = max(0.0, variable) / elapsed * (days - elapsed) if elapsed else 0.0
    budgets_by_name = {r["name"]: r for r in budget["categories"] if not r["parent"]}
    category_rows = []
    for name in sorted(groups.keys() | budgets_by_name.keys()):
        r = budgets_by_name.get(name, {})
        actual, target = round(groups.get(name, 0), 2), r.get("available")
        if name in ("Mortgage", "Loans") and name not in flags:
            target = None
        category_rows.append({"name": name, "spent": actual, "budget": target,
                              "planned": r.get("expected", 0), "remaining": round(target - actual, 2) if target is not None else None,
                              "warning": "over" if target is not None and actual > target else
                                         "near" if target is not None and target > 0 and actual >= target * 0.8 else "",
                              "classification": flags.get(name, "unallocated_debt" if name in ("Mortgage", "Loans") else "variable")})
    counts = dict(conn.execute(select(Transaction.account_id, func.count()).where(
        Transaction.posted >= start.isoformat(), Transaction.posted < end.isoformat()).group_by(Transaction.account_id)).fetchall())
    warnings = ["Balances and imported transactions are user-supplied; no statement reconciliation has been confirmed."]
    uncategorized = len({r["id"] for r in current if not r["category"]})
    if uncategorized:
        warnings.append(f"{uncategorized} transactions need categorization; uncategorized outflows are separate and may be transfers, not consumption.")
    debt = round(-sum(r["amount"] for r in current if kind(r) == "unallocated_debt"), 2)
    if debt:
        warnings.append("Unsplit mortgage or loan payments are separate from consumption. Split principal and interest from the lender statement; never guess the allocation.")
    missing = [a["display_name"] or a["name"] for a in accounts if not a["hidden"] and a["kind"] in ("checking", "savings", "credit") and not counts.get(a["id"])]
    if missing:
        warnings.append("Some visible accounts have no transactions in this month; coverage may be incomplete.")
    if any(a["hidden"] for a in accounts):
        warnings.append("Hidden accounts are excluded. Confirm this matches household coverage.")
    if any(not a["balance_date"] or a["balance_date"][:10] < (today - timedelta(days=7)).isoformat() for a in accounts if not a["hidden"]):
        warnings.append("Some account balances are missing an as-of date or are over seven days old.")
    if conn.execute(select(Transaction.id).where(Transaction.pending == 1).limit(1)).fetchone():
        warnings.append("Pending transactions are included using Runway's existing budget rules and may change.")
    subscriptions = db.rows(conn.execute(select(Recurring).where(Recurring.active == 1, Recurring.amount < 0)))
    subscriptions = [r for r in subscriptions if r["category"] and "subscription" in kinds.top(r["category"]).lower()
                     and (not account or r["account_id"] == account)]
    for r in subscriptions:
        r["monthly_estimate"] = round(-sum(r["amount"] for _ in forecast.scheduled(r, start - timedelta(days=1), end - timedelta(days=1))), 2)
    prior_start = dates.add_months(start, -1)
    prior_end = min(start, prior_start + timedelta(days=elapsed))
    previous = round(-sum(r["amount"] for r in rows if prior_start.isoformat() <= r["posted"] < prior_end.isoformat()
                          and kind(r) in ("fixed", "variable", "interest")), 2)
    return {"month": dates.month_key(start), "spent": spent, "fixed": fixed, "variable": round(variable, 2),
            "unallocated_debt": debt, "non_consumption": round(-sum(r["amount"] for r in current if kind(r) in ("transfer", "principal")), 2),
            "unclassified_outflow": round(-sum(r["amount"] for r in current if kind(r) == "unclassified" and r["amount"] < 0), 2),
            "remaining_estimate": round(remaining_fixed + max(pace, scheduled_variable), 2), "estimate_method": "Known fixed schedules plus the greater of variable schedules and variable spending pace (not added twice); not guaranteed bills or available cash.",
            "prior_comparable": previous, "elapsed_days": elapsed, "categories": category_rows,
            "merchants": [{"name": k, "spent": round(v, 2)} for k, v in sorted(merchants.items(), key=lambda x: -x[1])[:50]],
            "weekly": [{"week": k, "spent": round(v, 2)} for k, v in sorted(weeks.items())],
            "monthly": [{"month": dates.month_key(dates.add_months(start, -i)), "spent": round(monthly.get(dates.month_key(dates.add_months(start, -i)), 0), 2)} for i in range(3, -1, -1)],
            "transactions": current[:500], "subscriptions": subscriptions, "warnings": warnings,
            "missing_accounts": missing, "uncategorized": uncategorized, "reconciled": False,
            "last_dates": [{"name": a["display_name"] or a["name"], "balance_date": a["balance_date"], "hidden": bool(a["hidden"])} for a in accounts],
            "accounts": [{"id": a["id"], "name": a["display_name"] or a["name"], "kind": a["kind"]} for a in accounts if not a["hidden"] and a["kind"] in ("checking", "savings", "credit")],
            "classifications": flags}
