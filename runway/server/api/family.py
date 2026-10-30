"""Manual accounts and read-only Family Finance Hub projections."""
from __future__ import annotations

from collections.abc import Mapping
from datetime import date
from uuid import uuid4
from typing import cast

from sqlalchemy import insert, select, update

from ... import validate
from ...domain import family, forecast
from ...storage.models import Account
from ..common import ApiError
from ..contract import FamilyAccountBody, FamilyAccountReply, FamilyForecastBody, FamilyForecastReply

_v = validate.Validator(ApiError)


def api_family_account(conn, _q, body: FamilyAccountBody) -> FamilyAccountReply:
    """Create a manual account or update its balance. Connected accounts remain bank-controlled."""
    if not isinstance(body, dict):
        raise ApiError("Send an account")
    balance = _v.amount(body.get("balance"), "balance", required=True)
    day = _v.day(body.get("balance_date"), "balance date", True)
    if day > date.today().isoformat():
        raise ApiError("A balance date cannot be in the future")
    aid = _v.text(body.get("id"), "account", 200)
    if aid:
        account = conn.execute(select(Account).where(Account.id == aid)).fetchone()
        if not account:
            raise ApiError("Account not found", 404)
        if account["provider"] != "manual":
            raise ApiError("Only manual account balances can be edited here")
        conn.execute(update(Account).where(Account.id == aid).values(balance=balance, balance_date=day))
    else:
        name = _v.text(body.get("name"), "account name", 100, True)
        kind = body.get("kind", "checking")
        if kind not in ("checking", "savings", "credit"):
            raise ApiError("Choose checking, savings or credit")
        aid = "manual:" + uuid4().hex
        conn.execute(insert(Account).values(id=aid, name=name, kind=kind, balance=balance, balance_date=day,
                                           provider="manual", currency="USD"))
    return {"ok": True, "id": aid}


def _mapping(body: Mapping, key: str) -> dict:
    value = body.get(key, {})
    if not isinstance(value, dict) or len(value) > 500:
        raise ApiError("Send at most 500 scenario changes")
    return value


def api_family_forecast(conn, _q, body: FamilyForecastBody) -> FamilyForecastReply:
    """Run baseline and scenario through the same engine; never save overrides or move saved keys."""
    if not isinstance(body, dict):
        raise ApiError("Send a forecast request")
    start = date.fromisoformat(_v.day(body.get("start"), "starting date", True))
    # Balances mean 'as of start', not a reconstruction of historical balances.
    end = date(2026, 12, 31)
    if not date(2026, 1, 1) <= start <= date(2026, 11, 1):
        raise ApiError("Choose a starting date in 2026 on or before November 1")
    aid = _v.text(body.get("account_id"), "checking account", 200, True)
    assert aid is not None
    baseline, _ = forecast.project(conn, start, (end - start).days)
    if not any(a["id"] == aid and a["kind"] == "checking" for a in baseline["accounts"]):
        raise ApiError("Choose a checking account included in the forecast")
    balances = {key: _v.amount(value, "scenario balance", required=True)
                for key, value in _mapping(body, "balances").items()}
    cash = {a["id"] for a in baseline["accounts"]}
    if balances.keys() - cash:
        raise ApiError("Choose an account included in the forecast")
    edits = {key: _v.amount(value, "scenario amount", required=True)
             for key, value in _mapping(body, "edits").items()}
    events = {e["key"]: e for e in baseline["events"] if e.get("key")}
    if edits.keys() - events.keys():
        raise ApiError("Choose a scheduled payment in this forecast")
    for key, amount in edits.items():
        if events[key]["kind"] == "card" and amount > 0:
            raise ApiError("A card payment must be zero or negative")
    scenario, _ = forecast.project(conn, start, (end - start).days, balances=balances, edits=edits)
    return cast(FamilyForecastReply, {"start": start.isoformat(), "account_id": aid,
            "baseline": family.months(baseline, aid), "scenario": family.months(scenario, aid),
            "events": [{k: e[k] for k in ("key", "name", "date", "amount", "kind")}
                       for e in baseline["events"] if e["account_id"] == aid and e.get("key")],
            "warnings": baseline["warnings"], "scenario_warnings": scenario["warnings"]})
