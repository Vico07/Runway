"""Smart Card Planner uses only synthetic verified terms and never invents issuer benefits."""
from datetime import date
import json

from sqlalchemy import func, select, update

from runway.domain import cardplanner as cp, forecast
from runway.server.api.cardplanner import api_card_rule
from runway.storage.models import Account, Recurring, Transaction
from runway.storage import db
from tests import forecast_support as fs
from tests.shared import LedgerCase, TODAY, freeze_today


def terms(**extra):
    return {"credit_limit": 10000, "available_credit": 8000, "purchase_apr": 20, "closing_day": 10, "due_day": 5,
            "grace": "active", "carrying_interest": False, "source": "Synthetic issuer terms", "verified_on": TODAY.isoformat(),
            "rewards_verified": True, "rewards": [{"unit": "USD", "rate": 2}], **extra}


class PlannerTests(LedgerCase):
    def setUp(self):
        super().setUp()
        freeze_today(self)
        fs.card_setup(self)
        cp.save_profile(self.conn, "cc", terms(), TODAY)

    def quote(self, **extra):
        p = cp.purchase_values({"merchant": "Example groceries", "amount": 100, "category": "Groceries",
                                "date": "2026-09-24", "checking_id": "chk", "strategy": "full", **extra}, TODAY)
        return cp.quote(self.conn, p, TODAY)

    def test_verified_full_statement_rewards_and_explainable_recommendation(self):
        result = self.quote()
        o = result["options"][0]
        self.assertEqual(o["rewards"]["dollars"], 2)
        self.assertEqual(o["interest_estimate"], 0)
        self.assertEqual(o["net_cost"], 98)
        self.assertEqual((o["close"], o["due"]), ("2026-10-10", "2026-11-05"))
        self.assertEqual(result["recommendation"], "cc", o["reasons"])
        self.assertEqual(o["utilization"], 10)

    def test_quote_has_no_writes_and_purchase_is_not_immediate_checking_spend(self):
        baseline, _ = forecast.project(self.conn, TODAY, 90)
        fs.no_writes(self, AssertionError("Scenario attempted a database write"))
        result = self.quote()
        cash = result["options"][0]["cashflow"]
        i = cash["days"].index("2026-09-24")
        self.assertEqual(cash["balances"][i], baseline["accounts"][0]["series"][i])
        self.assertLess(cash["balances"][-1], baseline["accounts"][0]["series"][-1])
        self.assertEqual(forecast.project(self.conn, TODAY, 90)[0], baseline)

    def test_statement_timing_across_month_end_and_short_months(self):
        p = {"closing_day": 31, "due_day": 15}
        self.assertEqual(cp.timing(p, date(2027, 2, 5)), (date(2027, 2, 28), date(2027, 3, 15)))
        p["closing_day"] = 10
        self.assertEqual(cp.timing(p, date(2026, 9, 11)), (date(2026, 10, 10), date(2026, 10, 15)))
        self.assertIn("posting", " ".join(self.quote(date="2026-10-10")["options"][0]["reasons"]))

    def test_unknown_stale_terms_and_valuation_are_not_ranked(self):
        for changed in [{"grace": "unknown"}, {"purchase_apr": None}, {"verified_on": "2026-01-01"},
                        {"available_credit": None}, {"rewards_verified": False},
                        {"rewards": [{"unit": "miles", "rate": 2}]}]:
            with self.subTest(changed=changed):
                cp.save_profile(self.conn, "cc", terms(**changed), TODAY)
                self.assertIsNone(self.quote()["recommendation"])
                self.assertTrue(self.quote()["options"][0]["reasons"])

    def test_points_value_caps_and_reward_expiration(self):
        profile = cp.profile_values(terms(rewards=[{"unit": "miles", "rate": 2, "value": 0.015, "cap": 100, "used": 75}]), TODAY)
        p = cp.purchase_values({"merchant": "Example", "amount": 100, "date": "2026-09-24"}, TODAY)
        reward = cp.reward_value(profile, p)
        self.assertEqual(reward["units"], 50)
        self.assertEqual(reward["dollars"], .75)
        profile["rewards"][0]["expires"] = "2026-09-23"
        self.assertIsNone(cp.reward_value(profile, p)["dollars"])

    def test_insufficient_credit_interest_and_reserve_guards(self):
        cp.save_profile(self.conn, "cc", terms(available_credit=50), TODAY)
        self.assertIsNone(self.quote()["recommendation"])
        cp.save_profile(self.conn, "cc", terms(grace="lost", carrying_interest=True), TODAY)
        self.assertIsNone(self.quote()["recommendation"])
        result = self.quote(avoid_interest=False)["options"][0]
        self.assertGreater(result["interest_estimate"], 0)
        self.assertTrue(any("lost" in w for w in result["warnings"]))
        self.assertIsNone(self.quote(reserve=100000)["recommendation"])

    def test_minimum_and_custom_without_payoff_horizon_do_not_claim_known_total_cost(self):
        for strategy in ("minimum", "fixed", "custom"):
            option = self.quote(strategy=strategy, payment_amount=25)["options"][0]
            self.assertFalse(option["eligible"])
            self.assertTrue(any("payoff date" in r for r in option["reasons"]))
        self.assertTrue(self.quote(strategy="target", target_date="2027-01-10")["options"][0]["plan"]["pay_amount"] > 0)

    def test_target_date_alone_does_not_make_an_insufficient_custom_payment_a_payoff_plan(self):
        option = self.quote(strategy="custom", payment_amount=1, target_date="2027-01-10")["options"][0]
        self.assertFalse(option["eligible"])
        self.assertIsNone(option["interest_estimate"])
        self.assertIsNone(option["net_cost"])
        self.assertTrue(any("do not clear" in r for r in option["reasons"]))
        self.conn.execute(update(Account).where(Account.id == "cc").values(balance_date="2026-01-01"))
        self.assertTrue(any("card balance" in r for r in self.quote()["options"][0]["reasons"]))

    def test_expired_deferred_interest_and_mixed_balances_require_verification(self):
        cp.save_profile(self.conn, "cc", terms(promo_type="deferred", promo_balance=200,
                       promotional_apr=0, promo_starts="2026-01-01", promo_expires="2026-09-20", promo_verified=True), TODAY)
        option = self.quote(use_promotion=True, target_date="2026-12-01")["options"][0]
        self.assertFalse(option["eligible"])
        self.assertIsNotNone(option["deferred_interest_risk"])
        self.assertTrue(any("retroactively" in w for w in option["warnings"]))

    def test_saved_purchase_is_schedule_not_actual_spending_and_can_be_cancelled(self):
        count = self.conn.execute(select(func.count()).select_from(Transaction)).scalar()
        p = cp.save_purchase(self.conn, {"merchant": "Example purchase", "amount": 100, "category": "Groceries",
                            "date": "2026-09-24", "checking_id": "chk", "strategy": "full", "card_id": "cc"}, TODAY)
        r = self.conn.execute(select(Recurring).where(Recurring.id == p["recurring_id"])).fetchone()
        self.assertEqual((r["account_id"], r["amount"]), ("cc", -100))
        self.assertEqual(self.conn.execute(select(func.count()).select_from(Transaction)).scalar(), count)
        cp.cancel(self.conn, p["id"])
        self.assertEqual(self.conn.execute(select(Recurring.active).where(Recurring.id == p["recurring_id"])).scalar(), 0)
        self.assertEqual(json.loads(db.get_setting(self.conn, cp.PURCHASE + p["id"]))["status"], "cancelled")

    def test_rules_do_not_override_safety_and_are_persistent(self):
        api_card_rule(self.conn, {}, {"data": {"card_id": "cc", "merchant": "Example", "require_grace": True, "max_balance": 950}})
        result = self.quote()
        self.assertIsNone(result["recommendation"])
        self.assertTrue(any("rule" in r.lower() for r in result["options"][0]["reasons"]))
        self.assertIn("Example", db.get_setting(self.conn, cp.RULES))

    def test_invalid_numeric_terms_and_future_verification(self):
        for changed in ({"purchase_apr": "nan"}, {"available_credit": -1}, {"verified_on": "2099-01-01"}, {"closing_day": 32}):
            with self.subTest(changed=changed), self.assertRaises(ValueError):
                cp.save_profile(self.conn, "cc", terms(**changed), TODAY)

    def test_missing_issuer_statement_and_hidden_card_are_not_ranked(self):
        self.conn.execute(update(Account).where(Account.id == "cc").values(plaid_account_id=None))
        self.assertIsNone(self.quote()["recommendation"])
        self.conn.execute(update(Account).where(Account.id == "cc").values(hidden=1))
        self.assertEqual(self.quote()["options"], [])
