"""The Smart Card Planner's verified manual terms and explicit schedule saves."""
from __future__ import annotations

import json
from datetime import date
from typing import Any

from sqlalchemy import select

from ... import validate
from ...domain import cardplanner, forecast
from ...storage import db
from ...storage.models import Account, Recurring
from ..common import ApiError
from ..contract import FamilyModuleBody, FamilyModuleReply

_v = validate.Validator(ApiError)


def _data(body):
    data = body.get("data") if isinstance(body, dict) else None
    if not isinstance(data, dict):
        raise ApiError("Send planner data as an object")
    return data


def api_cardplanner(conn, _q, _b) -> FamilyModuleReply:
    accounts = db.rows(conn.execute(select(Account).where(Account.hidden == 0).order_by(Account.name)))
    cards = [a for a in accounts if a["kind"] == "credit"]
    for c in cards:
        c["statement"] = forecast.bank_statement(conn, c, date.today())
        c["payment_plan"] = forecast.payment_plan(conn, c["id"])
    plans = list(cardplanner.stored(conn, cardplanner.PURCHASE).values())
    for p in plans:
        recurring = conn.execute(select(Recurring.amount, Recurring.active, Recurring.anchor_date).where(Recurring.id == p["recurring_id"])).fetchone()
        p["schedule_changed"] = not recurring or recurring["amount"] != -p["amount"] or recurring["anchor_date"] != p["date"]
        p["schedule_active"] = bool(recurring and recurring["active"])
    return {"data": {"cards": cards, "profiles": cardplanner.stored(conn, cardplanner.PROFILE),
                     "checking": [a for a in accounts if a["kind"] == "checking"], "purchases": plans,
                     "rules": json.loads(db.get_setting(conn, cardplanner.RULES) or "[]")}}


def api_card_profile(conn, _q, body: FamilyModuleBody) -> FamilyModuleReply:
    data = _data(body)
    aid = _v.text(data.get("card_id"), "card", 200, True)
    assert aid is not None
    try:
        return {"data": cardplanner.save_profile(conn, aid, data, date.today())}
    except (ValueError, LookupError) as e:
        raise ApiError(str(e)) from e


def api_card_quote(conn, _q, body: FamilyModuleBody) -> FamilyModuleReply:
    try:
        return {"data": cardplanner.quote(conn, cardplanner.purchase_values(_data(body), date.today()), date.today())}
    except ValueError as e:
        raise ApiError(str(e)) from e


def api_card_purchase(conn, _q, body: FamilyModuleBody) -> FamilyModuleReply:
    try:
        return {"data": cardplanner.save_purchase(conn, _data(body), date.today())}
    except ValueError as e:
        raise ApiError(str(e)) from e


def api_card_cancel(conn, _q, _b, pid) -> FamilyModuleReply:
    try:
        cardplanner.cancel(conn, pid)
    except ValueError as e:
        raise ApiError(str(e)) from e
    return {"data": {"ok": True}}


def api_card_rule(conn, _q, body: FamilyModuleBody) -> FamilyModuleReply:
    data = _data(body)
    aid = _v.text(data.get("card_id"), "card", 200, True)
    assert aid is not None
    try:
        cardplanner.card(conn, aid)
    except ValueError as e:
        raise ApiError(str(e)) from e
    rule: dict[str, Any] = {"card_id": aid, "merchant": _v.text(data.get("merchant"), "merchant", 100),
            "category": _v.text(data.get("category"), "category", 100),
            "require_grace": validate.on(data.get("require_grace", True)),
            "require_promotion": validate.on(data.get("require_promotion")), "require_cap": validate.on(data.get("require_cap"))}
    for key in ("max_balance", "min_available", "reserve"):
        value = _v.amount(data.get(key), key)
        if value is not None and value < 0:
            raise ApiError("Rule thresholds must be nonnegative")
        rule[key] = value
    rules = json.loads(db.get_setting(conn, cardplanner.RULES) or "[]")
    # Editing a preference replaces the same merchant/category rule. Removal is explicit.
    rules = [r for r in rules if (r.get("merchant"), r.get("category")) != (rule["merchant"], rule["category"])]
    if not validate.on(data.get("remove")):
        if len(rules) >= 100:
            raise ApiError("At most 100 spending rules")
        rules.append(rule)
    db.set_setting(conn, cardplanner.RULES, json.dumps(rules))
    return {"data": {"rules": rules}}
