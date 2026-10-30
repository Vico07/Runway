"""Manual verified card terms and explainable hypothetical purchases, using the existing cash-flow engine."""
from __future__ import annotations

import json
import math
from datetime import date, timedelta
from uuid import uuid4
from typing import Any

from sqlalchemy import insert, select, update

from . import bankdays, budgets, categories, forecast, statements
from .. import dates, validate
from ..storage import db, settings_keys as sk
from ..storage.models import Account, Category, Recurring, Setting

PROFILE = "family_card_profile:"
PURCHASE = "family_purchase:"
RULES = "family_card_rules"
_v = validate.Validator(ValueError)
STRATEGIES = ("existing", "full", "minimum", "fixed", "custom", "target")


def stored(conn, prefix: str) -> dict[str, dict]:
    return {r["key"][len(prefix):]: json.loads(r["value"]) for r in conn.execute(select(Setting.key, Setting.value).where(Setting.key.startswith(prefix)))}


def card(conn, aid: str) -> dict:
    row = conn.execute(select(Account).where(Account.id == aid, Account.kind == "credit", Account.hidden == 0)).fetchone()
    if not row:
        raise ValueError("Choose a visible credit card account; add manual cards in Family Finance Hub first")
    return dict(row)


def profile_values(data: dict, today: date) -> dict:
    out: dict[str, Any] = {}
    for key in ("credit_limit", "available_credit", "purchase_apr", "promotional_apr", "foreign_fee", "statement_balance", "minimum_payment", "promo_balance", "promo_minimum", "balance_threshold"):
        value = _v.number(data.get(key), key.replace("_", " "), 0, 100) if key.endswith("apr") or key == "foreign_fee" else _v.amount(data.get(key), key.replace("_", " "))
        if value is not None and (value < 0 or (key.endswith("apr") and value > 100)):
            raise ValueError("Amounts must be nonnegative and APRs no more than 100%")
        out[key] = value
    for key in ("closing_day", "due_day"):
        out[key] = _v.integer(data.get(key), key.replace("_", " "), 1, 31)
    for key in ("verified_on", "last_close", "next_due", "promo_starts", "promo_expires", "promo_payoff_date"):
        out[key] = _v.day(data.get(key), key.replace("_", " "))
    if out["verified_on"] and out["verified_on"] > today.isoformat():
        raise ValueError("Verification date cannot be in the future")
    out["source"] = _v.text(data.get("source"), "data source", 300)
    out["grace"] = data.get("grace", "unknown")
    if out["grace"] not in ("active", "lost", "unknown"):
        raise ValueError("Choose active, lost or unknown grace period")
    out["carrying_interest"] = data.get("carrying_interest") if isinstance(data.get("carrying_interest"), bool) else None
    out["rewards_verified"] = validate.on(data.get("rewards_verified"))
    out["promo_verified"] = validate.on(data.get("promo_verified"))
    out["promo_type"] = data.get("promo_type", "none")
    if out["promo_type"] not in ("none", "introductory", "deferred"):
        raise ValueError("Choose a promotion type")
    rewards = data.get("rewards", [])
    if not isinstance(rewards, list) or len(rewards) > 50:
        raise ValueError("Send at most 50 reward terms")
    out["rewards"] = []
    for reward in rewards:
        if not isinstance(reward, dict):
            raise ValueError("Each reward term must be an object")
        unit = _v.text(reward.get("unit"), "reward unit", 40, True)
        rate = _v.number(reward.get("rate"), "reward rate", 0, 1000, required=True)
        valuation = _v.number(reward.get("value"), "dollars per reward unit", 0, 100)
        cap, used = _v.amount(reward.get("cap"), "eligible spending cap"), _v.amount(reward.get("used", 0), "cap spending already used", required=True)
        if (cap is not None and cap < 0) or used < 0:
            raise ValueError("Reward caps and usage must be nonnegative")
        out["rewards"].append({"unit": unit, "rate": rate, "value": valuation, "cap": cap, "used": used,
                               "merchant": _v.text(reward.get("merchant"), "reward merchant", 100),
                               "category": _v.text(reward.get("category"), "reward category", 100),
                               "starts": _v.day(reward.get("starts"), "reward start"), "expires": _v.day(reward.get("expires"), "reward expiry")})
    restrictions = data.get("restrictions", {})
    if not isinstance(restrictions, dict):
        raise ValueError("Restrictions must be an object")
    out["restrictions"] = {}
    for key in ("excluded_merchants", "excluded_categories"):
        items = restrictions.get(key, [])
        if not isinstance(items, list) or len(items) > 50:
            raise ValueError("Restriction lists must have at most 50 items")
        out["restrictions"][key] = [_v.text(v, "restriction", 100, True) for v in items]
    out["restrictions"]["domestic_only"] = validate.on(restrictions.get("domestic_only"))
    return out


def save_profile(conn, aid: str, data: dict, today: date) -> dict:
    card(conn, aid)
    out = profile_values(data, today)
    if out["last_close"] or out["next_due"] or out["statement_balance"] is not None:
        if not (out["last_close"] and out["next_due"] and out["statement_balance"] is not None):
            raise ValueError("Enter the actual closing date, due date and statement balance together")
        statements.add(conn, aid, {"statement_date": out["last_close"], "due_date": out["next_due"], "balance": out["statement_balance"], "minimum_payment": out["minimum_payment"]}, today)
    db.set_setting(conn, PROFILE + aid, json.dumps(out))
    return out


def purchase_values(data: dict, today: date) -> dict:
    amount = _v.amount(data.get("amount"), "purchase amount", required=True)
    if amount <= 0:
        raise ValueError("Enter a positive purchase amount")
    day = _v.day(data.get("date"), "purchase date", True)
    if not today.isoformat() <= day <= (today + timedelta(days=300)).isoformat():
        raise ValueError("Plan a purchase from today through the next 300 days")
    strategy = data.get("strategy", "full")
    if strategy not in STRATEGIES:
        raise ValueError("Choose a supported repayment strategy")
    target = _v.day(data.get("target_date"), "payoff target date")
    if target and (target < day or target > (today + timedelta(days=365)).isoformat()):
        raise ValueError("Payoff target must be after the purchase and within a year")
    payment = _v.amount(data.get("payment_amount"), "payment amount")
    if strategy in ("fixed", "custom") and (payment is None or payment <= 0):
        raise ValueError("Enter a positive fixed/custom payment")
    if strategy == "target" and not target:
        raise ValueError("Enter a payoff target date")
    reserve = _v.amount(data.get("reserve", 0), "checking reserve", required=True)
    if reserve < 0:
        raise ValueError("Checking reserve must be nonnegative")
    frequency = data.get("frequency", "once")
    if frequency not in ("once", "monthly"):
        raise ValueError("Choose one-time or monthly")
    return {"merchant": _v.text(data.get("merchant"), "merchant", 150, True), "category": _v.text(data.get("category"), "budget category", 100),
            "amount": amount, "date": day, "strategy": strategy, "target_date": target, "payment_amount": payment,
            "reserve": reserve, "checking_id": _v.text(data.get("checking_id"), "checking account", 200),
            "frequency": frequency, "avoid_interest": data.get("avoid_interest", True) is not False,
            "use_promotion": validate.on(data.get("use_promotion")), "foreign": validate.on(data.get("foreign")),
            "preferred_card": _v.text(data.get("preferred_card"), "preferred card", 200), "notes": _v.text(data.get("notes"), "notes", 1000)}


def timing(p: dict, day: date) -> tuple[date, date]:
    close = day.replace(day=min(p["closing_day"], dates.days_in_month(day)))
    if close < day:
        close = dates.add_months(close, 1, p["closing_day"])
    due = dates.next_after(close, p["due_day"])
    return close, due


def reward_value(profile: dict, purchase: dict) -> dict:
    applicable = []
    for r in profile.get("rewards", []):
        if r["merchant"] and r["merchant"].casefold() not in purchase["merchant"].casefold():
            continue
        if r["category"] and r["category"].casefold() != (purchase["category"] or "").casefold():
            continue
        if (r["starts"] and purchase["date"] < r["starts"]) or (r["expires"] and purchase["date"] > r["expires"]):
            continue
        eligible = purchase["amount"] if r["cap"] is None else min(purchase["amount"], max(0, r["cap"] - r["used"]))
        units = eligible * r["rate"] / (100 if r["unit"] == "USD" else 1)
        dollars = units if r["unit"] == "USD" else units * r["value"] if r["value"] is not None else None
        applicable.append({"units": round(units, 4), "unit": r["unit"], "dollars": None if dollars is None else round(dollars, 2),
                           "cap_remaining": None if r["cap"] is None else max(0, r["cap"] - r["used"]), "eligible_spend": eligible})
    if not applicable:
        return {"units": 0, "unit": "unverified", "dollars": None, "cap_remaining": None, "eligible_spend": 0}
    # Unknown valuations cannot win a comparison against a priced reward.
    return max(applicable, key=lambda r: r["dollars"] if r["dollars"] is not None else -1)


def planned_item(p: dict, aid: str, rid: int = -1) -> dict:
    return {"id": rid, "name": p["merchant"], "account_id": aid, "amount": -p["amount"], "frequency": p["frequency"],
            "anchor_date": p["date"], "category": p["category"], "amount_mode": "fixed", "amount_min": None, "amount_max": None,
            "match": p["merchant"], "end_date": None, "active": 1, "dates": None}


def quote(conn, p: dict, today: date) -> dict:
    day = dates.parse_day(p["date"])
    if p["category"] and not conn.execute(select(Account.id).limit(1)).fetchone():
        raise ValueError("Add an account first")
    if p["category"] and p["category"] not in {c["name"] for c in categories.all_categories(conn)}:
        raise ValueError("Choose an existing budget category")
    profiles = stored(conn, PROFILE)
    cards = db.rows(conn.execute(select(Account).where(Account.kind == "credit", Account.hidden == 0).order_by(Account.name)))
    horizon = min(365, max(90, (day - today).days + 65, (dates.parse_day(p["target_date"]) - today).days if p["target_date"] else 0))
    before, _ = forecast.project(conn, today, horizon)
    checking = next((a for a in before["accounts"] if a["kind"] == "checking" and (not p["checking_id"] or a["id"] == p["checking_id"])), None)
    if not checking:
        raise ValueError("Choose a checking account included in the cash-flow forecast")
    out = []
    for a in cards:
        profile = profiles.get(a["id"], {})
        reasons, warnings = [], []
        owed = max(0.0, forecast.owed(a))
        verified = profile.get("verified_on")
        if not verified or not profile.get("source") or not (today - timedelta(days=30)).isoformat() <= verified <= today.isoformat():
            reasons.append("Verify the card terms and source within the last 30 days")
        for key in ("closing_day", "due_day", "purchase_apr", "credit_limit", "available_credit"):
            if profile.get(key) is None:
                reasons.append("Verify " + key.replace("_", " "))
        if profile.get("grace", "unknown") == "unknown":
            reasons.append("Grace period is unknown; verify issuer terms")
        if profile.get("carrying_interest") is None:
            reasons.append("Verify whether the card carries an interest-bearing balance")
        if p["avoid_interest"] and (profile.get("carrying_interest") or profile.get("grace") == "lost"):
            reasons.append("Rule excludes new purchases on interest-bearing balances")
        if profile.get("credit_limit") is not None and profile["credit_limit"] <= 0:
            reasons.append("Verify a positive credit limit")
        if p["use_promotion"] and owed > (profile.get("promo_balance") or 0):
            reasons.append("Mixed standard and promotional balances require a separate issuer payoff plan; no promotional ranking is safe")
        if profile.get("available_credit") is not None and p["amount"] > profile["available_credit"]:
            reasons.append("Purchase exceeds verified available credit")
        restrictions = profile.get("restrictions", {})
        if any(v.casefold() in p["merchant"].casefold() for v in restrictions.get("excluded_merchants", [])) or (p["category"] or "").casefold() in [v.casefold() for v in restrictions.get("excluded_categories", [])]:
            reasons.append("Purchase conflicts with a card restriction")
        if p["foreign"] and restrictions.get("domestic_only"):
            reasons.append("Card is restricted to domestic purchases")
        if p["foreign"] and profile.get("foreign_fee") is None:
            reasons.append("Verify the foreign transaction fee")
        if a["pay_from"] != checking["id"]:
            reasons.append("Choose this checking account as the card's paying account in Family Finance Hub")
        bank = forecast.bank_statement(conn, a, today)
        if not bank or bank.get("stale"):
            reasons.append("Enter a current issuer statement before relying on cash-flow impact")
        if not a.get("balance_date") or a["balance_date"][:10] < (today - timedelta(days=7)).isoformat():
            reasons.append("Refresh the card balance before relying on utilization and payment estimates")
        if a.get("currency") not in (None, "USD"):
            reasons.append("USD cash-flow comparison cannot assume a foreign exchange rate")
        cash_date = conn.execute(select(Account.balance_date).where(Account.id == checking["id"])).scalar()
        if not cash_date or cash_date[:10] < (today - timedelta(days=7)).isoformat():
            reasons.append("Refresh the checking balance before relying on the reserve check")
        if bank and profile.get("closing_day") and profile.get("due_day"):
            last = dates.parse_day(bank["last_statement_date"])
            if bank["closing_day"] != min(profile["closing_day"], dates.days_in_month(last)) or bank["due_day"] != profile["due_day"]:
                reasons.append("Profile cycle days disagree with the issuer statement; verify before planning")
        rewards = reward_value(profile, p)
        if not profile.get("rewards_verified") or rewards["dollars"] is None:
            reasons.append("Verify applicable rewards and an explicit dollar valuation (or a verified zero-reward term)")
        apr = profile.get("purchase_apr")
        if p["use_promotion"]:
            if not (profile.get("promo_type") in ("introductory", "deferred") and profile.get("promo_verified") and profile.get("promo_starts") and profile.get("promo_expires")
                    and profile["promo_starts"] <= p["date"] <= profile["promo_expires"] and profile.get("promotional_apr") is not None):
                reasons.append("Verify promotion APR, eligibility and effective dates")
            elif not p["target_date"] or p["target_date"] > profile["promo_expires"]:
                reasons.append("Promotion requires a payoff plan on or before its deadline")
            elif p["amount"] < (profile.get("promo_minimum") or 0):
                reasons.append("Purchase is below the promotional financing minimum")
            else:
                apr = profile["promotional_apr"]
            if profile.get("promo_type") == "deferred":
                warnings.append("Deferred interest can apply retroactively to the original purchase if the deadline is missed; this estimate assumes on-time payoff")
        if (profile.get("promo_type") == "deferred" and (profile.get("promo_balance") or 0) > 0
                and (not profile.get("promo_payoff_date") or not profile.get("promo_expires")
                     or profile["promo_payoff_date"] > profile["promo_expires"] or profile["promo_expires"] < today.isoformat())):
            reasons.append("Protect the existing deferred-interest balance with a verified payoff plan")
        close = due = None
        if profile.get("closing_day") and profile.get("due_day"):
            effective_day = bankdays.settles(day, False)
            close, due = timing(profile, effective_day)
            nominal_close, _ = timing(profile, day)
            if nominal_close != close:
                reasons.append("Business-day settlement crosses a statement close; issuer posting must be verified")
            if effective_day != day:
                warnings.append("Runway models this scheduled purchase on the next business day; the issuer's actual posting date may differ")
            if day in (close, nominal_close):
                reasons.append("Purchase is on the closing day; posting may fall into either statement cycle")
        mode = p["strategy"]
        plan = forecast.payment_plan(conn, a["id"], apr)
        if mode != "existing":
            plan = {"pay_mode": "fixed" if mode in ("fixed", "custom", "target") else mode, "pay_amount": p["payment_amount"], "apr": apr}
        if plan["pay_mode"] != "full" and not p["target_date"]:
            reasons.append("A minimum/fixed payment alone has no known payoff date; total borrowing cost is unknown")
        if plan["pay_mode"] != "full" and p["frequency"] == "monthly":
            reasons.append("An ongoing recurring purchase has no final payoff horizon; compare it with full-statement repayment")
        if mode == "target" and due and p["target_date"]:
            if p["target_date"] < due.isoformat():
                reasons.append("Target is before the next scheduled payment; an extra issuer payment would be required")
            months = 1
            next_due = dates.add_months(due, 1, profile["due_day"])
            while next_due.isoformat() <= p["target_date"]:
                months += 1
                next_due = dates.add_months(next_due, 1, profile["due_day"])
            cushion = (owed + p["amount"]) * (apr or 0) / 100 * months / 12
            plan["pay_amount"] = math.ceil((owed + p["amount"] + cushion) / months * 100) / 100
            warnings.append("Target-date payment is a conservative installment estimate, not an issuer payoff quote; verify final payoff and interest")
        interest = None
        if apr is not None and due:
            stop = dates.parse_day(p["target_date"]) if p["target_date"] and plan["pay_mode"] != "full" else due
            free = profile.get("grace") == "active" and not profile.get("carrying_interest") and plan["pay_mode"] == "full" and stop <= due
            interest = 0.0 if free else round(p["amount"] * apr / 100 / 365 * max(0, (stop - day).days), 2)
        if plan["pay_mode"] != "full" and (not p["target_date"] or p["frequency"] == "monthly"):
            interest = None
        fees = round(p["amount"] * (profile.get("foreign_fee") or 0) / 100, 2) if p["foreign"] else 0.0
        cash = None
        if bank and due and a["pay_from"] == checking["id"]:
            after, _ = forecast.project(conn, today, horizon, planned=[planned_item(p, a["id"])], plans={a["id"]: plan})
            changed = next(v for v in after["accounts"] if v["id"] == checking["id"])
            cash = {"before_low": checking["low"], "after_low": changed["low"], "days": after["dates"], "balances": changed["series"],
                    "payment_events": [e for e in after["events"] if e.get("card_id") == a["id"]], "warnings": after["warnings"]}
            if p["target_date"] and plan["pay_mode"] != "full":
                by_target = [e for e in cash["payment_events"] if due.isoformat() <= e["date"] <= p["target_date"]]
                last_payment = by_target[-1] if by_target else None
                statement = (last_payment or {}).get("estimate", {}).get("statement")
                if last_payment is None or statement is None or statement + last_payment["amount"] > 0.01:
                    reasons.append("The projected payments do not clear the statement by the target date; total borrowing cost is unknown")
                    interest = None
            if changed["low"]["balance"] < p["reserve"]:
                reasons.append("Projected checking balance falls below the required household reserve")
            if after["warnings"]:
                reasons.append("Resolve cash-flow forecast warnings before treating this as a safe recommendation")
        utilized = None if not profile.get("credit_limit") else round((owed + p["amount"]) / profile["credit_limit"] * 100, 2)
        if utilized is not None and utilized > 100:
            reasons.append("Purchase would exceed the credit limit")
        if profile.get("grace") == "lost":
            warnings.append("Grace period is lost; changing the purchase date does not restore an interest-free period")
        if profile.get("balance_threshold") is not None and owed + p["amount"] > profile["balance_threshold"]:
            reasons.append("Purchase exceeds the configured card balance threshold")
        net = None if interest is None or rewards["dollars"] is None else round(p["amount"] + interest + fees - rewards["dollars"], 2)
        out.append({"card_id": a["id"], "name": db.account_label(a), "eligible": not reasons, "reasons": reasons, "warnings": warnings,
                    "rewards": rewards, "interest_estimate": interest, "fees": fees, "net_cost": net, "utilization": utilized,
                    "close": close.isoformat() if close else None, "due": due.isoformat() if due else None, "cashflow": cash, "plan": plan,
                    "deferred_interest_risk": round(p["amount"] * (profile.get("purchase_apr") or 0) / 100 / 365 * max(0, (dates.parse_day(profile["promo_expires"]) - day).days), 2) if profile.get("promo_expires") and profile.get("promo_type") == "deferred" else None})
    rules = json.loads(db.get_setting(conn, RULES) or "[]")
    applicable = [r for r in rules if (not r.get("merchant") or r["merchant"].casefold() in p["merchant"].casefold()) and (not r.get("category") or r["category"] == p["category"])]
    for option in out:
        profile = profiles.get(option["card_id"], {})
        for rule in applicable:
            if rule["card_id"] != option["card_id"]:
                continue
            failed = []
            owned = max(0.0, forecast.owed(next(a for a in cards if a["id"] == option["card_id"])))
            if rule.get("require_grace") and profile.get("grace") != "active":
                failed.append("active grace period")
            if rule.get("max_balance") is not None and owned + p["amount"] > rule["max_balance"]:
                failed.append("balance threshold")
            if rule.get("min_available") is not None and (profile.get("available_credit") or 0) - p["amount"] < rule["min_available"]:
                failed.append("available-credit reserve")
            if rule.get("require_promotion") and not (p["use_promotion"] and profile.get("promo_verified")):
                failed.append("active verified promotion")
            if rule.get("require_cap") and option["rewards"]["eligible_spend"] < p["amount"]:
                failed.append("unexhausted category bonus cap")
            if rule.get("reserve") is not None and (not option["cashflow"] or option["cashflow"]["after_low"]["balance"] < rule["reserve"]):
                failed.append("checking reserve")
            if failed:
                option["reasons"].append("Preference rule conditions not met: " + ", ".join(failed))
                option["eligible"] = False
        option["preferred"] = option["card_id"] == p["preferred_card"] or any(r["card_id"] == option["card_id"] for r in applicable)
        if option["preferred"] and not option["eligible"]:
            option["warnings"].append("The preferred card is currently unsuitable; its safety conditions are not met")
    ranked = sorted((r for r in out if r["eligible"] and r["net_cost"] is not None),
                    key=lambda r: (r["interest_estimate"] + r["fees"] > 0, r["interest_estimate"] + r["fees"], r["net_cost"], not r["preferred"], r["card_id"]))
    debit, _ = forecast.project(conn, today, horizon, planned=[planned_item(p, checking["id"])])
    debit_checking = next(a for a in debit["accounts"] if a["id"] == checking["id"])
    targets = budgets.load(conn)
    totals = budgets.month_totals(conn, dates.month_start(day), dates.add_months(dates.month_start(day), 1))
    target = budgets.amount_in(targets[p["category"]], dates.month_key(day)) if p["category"] in targets else None
    actual = -totals.get(p["category"], 0)
    income_categories = set(conn.execute(select(Category.name).where(Category.is_income == 1, Category.name != "Refunds")).scalars())
    payday = next((e for e in before["events"] if e["account_id"] == checking["id"] and e["amount"] > 0 and e.get("category") in income_categories), None)
    until_pay = [v for d, v in zip(before["dates"], checking["series"], strict=True) if payday and d < payday["date"]]
    safe = max(0, round(min(until_pay or [checking["balance"]]) - p["reserve"], 2)) if payday else None
    return {"purchase": p, "options": out, "safe_to_spend_until_paycheck": safe,
            "next_paycheck": {"date": payday["date"], "expected_amount": payday["amount"], "verified": False} if payday else None, "recommendation": ranked[0]["card_id"] if ranked else None,
            "explanation": "Eligible cards are ordered by avoiding interest/fees, protecting credit and reserve, then verified net cost. Uncertain options are not ranked.",
            "debit": {"net_cost": p["amount"], "low": debit_checking["low"], "reserve_protected": debit_checking["low"]["balance"] >= p["reserve"]},
            "budget": {"category": p["category"], "target": target, "actual": round(actual, 2), "planned": p["amount"],
                       "remaining_after": None if target is None else round(target - actual - p["amount"], 2)},
            "notice": "Estimates, not issuer quotes. Reward caps/usage and terms must be verified manually. A card purchase is planned category spending; its repayment is a transfer, never a second expense. Cash-flow budgets may already allow for the purchase."}


def save_purchase(conn, data: dict, today: date) -> dict:
    p = purchase_values(data, today)
    aid = _v.text(data.get("card_id"), "card", 200, True)
    assert aid is not None
    card(conn, aid)
    # Saving is explicit, but uncertain terms still require verification instead of persisting a misleading plan.
    option = next(r for r in quote(conn, p, today)["options"] if r["card_id"] == aid)
    if not option["eligible"]:
        raise ValueError("Resolve the selected card's verification and safety warnings before saving")
    values = planned_item(p, aid)
    values.pop("id")
    rid = conn.execute(insert(Recurring).values(**values).returning(Recurring.id)).scalar()
    pid = uuid4().hex
    record = {**p, "id": pid, "card_id": aid, "recurring_id": rid, "status": "planned", "estimated_rewards": option["rewards"], "estimated_interest": option["interest_estimate"]}
    db.set_setting(conn, PURCHASE + pid, json.dumps(record))
    if p["strategy"] != "existing":
        for key, value in ((sk.card_pay_mode(aid), option["plan"]["pay_mode"]), (sk.card_pay_amount(aid), option["plan"]["pay_amount"]), (sk.card_apr(aid), option["plan"]["apr"])):
            db.set_setting(conn, key, value)
    return record


def cancel(conn, pid: str) -> None:
    raw = db.get_setting(conn, PURCHASE + pid)
    if not raw:
        raise ValueError("Planned purchase not found")
    record = json.loads(raw)
    conn.execute(update(Recurring).where(Recurring.id == record["recurring_id"]).values(active=0))
    record["status"] = "cancelled"
    db.set_setting(conn, PURCHASE + pid, json.dumps(record))
