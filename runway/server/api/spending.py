"""Budget & Spending reuses the existing budget, category and transaction import handlers."""
from __future__ import annotations

import csv
import io
import json
from typing import cast

from sqlalchemy import select, update

from ... import validate
from ...domain import categories, spending
from ...storage import db
from ...storage.models import Account, Category, Transaction
from ..common import ApiError, _month_range
from ..contract import FamilyModuleBody, FamilyModuleReply
from .budget import api_budget
from .transactions import api_tx_import

_v = validate.Validator(ApiError)


def api_spending(conn, q, _b) -> FamilyModuleReply:
    start, end = _month_range(q)
    account, category = (q.get("account") or [""])[0], (q.get("category") or [""])[0]
    if account and not conn.execute(select(Account.id).where(Account.id == account, Account.hidden == 0, Account.kind.in_(["checking", "savings", "credit"]))).fetchone():
        raise ApiError("Choose a visible checking, savings or card account")
    if category and not conn.execute(select(Category.name).where(Category.name == category)).fetchone():
        raise ApiError("Choose an existing category")
    return {"data": spending.overview(conn, start, end, cast(dict, api_budget(conn, q, {})),
                                      (q.get("account") or [""])[0], (q.get("category") or [""])[0])}


def api_spending_classify(conn, _q, body: FamilyModuleBody) -> FamilyModuleReply:
    data = body.get("data")
    if not isinstance(data, dict):
        raise ApiError("Send a category classification")
    name = _v.text(data.get("category"), "category", 100, True)
    assert name is not None
    choice = data.get("classification")
    if name in ("Mortgage", "Loans") and choice not in ("principal", "transfer", "unallocated_debt"):
        raise ApiError("Split principal and interest into separate categories using the actual lender statement")
    if choice not in spending.CLASSES:
        raise ApiError("Choose a supported expense classification")
    existing = conn.execute(select(Category).where(Category.name == name)).fetchone()
    try:
        if not existing:
            categories.add(conn, name, "Transfer" if choice in ("principal", "transfer") else None)
        elif choice in ("principal", "transfer") and not existing["is_transfer"]:
            categories.move(conn, name, "Transfer")
        elif existing["is_transfer"] and choice not in ("principal", "transfer"):
            raise ApiError("Transfer categories cannot be reclassified as consumption here")
    except ValueError as e:
        raise ApiError(str(e)) from e
    values = spending.classes(conn)
    values[name] = choice
    db.set_setting(conn, spending.CLASS_KEY, json.dumps(values))
    return {"data": {"ok": True}}


def api_spending_import(conn, _q, body: FamilyModuleBody) -> FamilyModuleReply:
    data = body.get("data")
    if not isinstance(data, dict):
        raise ApiError("Send a CSV import")
    raw = _v.text(data.get("csv"), "CSV", 500_000, True)
    try:
        reader = csv.DictReader(io.StringIO(cast(str, raw).lstrip("\ufeff")), strict=True)
        if not {"date", "amount", "description"} <= set(reader.fieldnames or []):
            raise ApiError("CSV needs date, amount and description headers; merchant and category are optional")
        rows: list[dict] = []
        for row in reader:
            if len(rows) >= 500:
                raise ApiError("Import at most 500 rows at once")
            if None in row or any(v is None for v in row.values()):
                raise ApiError("Every CSV row must have the same columns as the header")
            rows.append(row)
    except csv.Error:
        raise ApiError("The CSV could not be read") from None
    result = api_tx_import(conn, {}, {"account": data.get("account"), "transactions": [
        {"posted": r["date"], "amount": r["amount"], "payee": r.get("merchant") or r["description"],
         "category": r.get("category") or None} for r in rows]})
    for item in result["rows"]:
        if item["status"] == "added":
            conn.execute(update(Transaction).where(Transaction.id == item["id"]).values(description=rows[item["i"]]["description"]))
    return {"data": result}
