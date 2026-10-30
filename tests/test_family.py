"""Family Hub uses Runway's schedules, card cycles and daily balances, without saving a scenario."""
from datetime import date
from unittest import mock

from sqlalchemy import insert, select

from runway.domain import forecast
from runway.server.api.family import api_family_account, api_family_forecast
from runway.server.api.recurring import api_recurring_add
from runway.server.api.accounts import api_account_update
from runway.server.common import ApiError
from runway.storage.models import Account, Override, Recurring
from tests import forecast_support as fs
from tests.shared import LedgerCase, freeze_today


class FamilyTests(LedgerCase):
    def setUp(self):
        super().setUp()
        freeze_today(self, date(2026, 10, 29))
        fs.card_setup(self)
        self.stmt("cc", 800, "2026-10-20", "2026-11-05", minimum=40)

    def request(self, **kw):
        return api_family_forecast(self.conn, {}, {"start": "2026-11-01", "account_id": "chk", **kw})

    def payment(self, amount=-100):
        return api_recurring_add(self.conn, {}, {"name": "Example bill", "account_id": "chk", "amount": amount,
                                               "frequency": "monthly", "anchor_date": "2026-11-10",
                                               "amount_mode": "fixed", "active": 1})

    def test_daily_months_and_december_carries_november(self):
        self.payment()
        result = self.request()
        nov, dec = result["baseline"]
        self.assertEqual((len(nov["days"]), len(dec["days"])), (30, 31))
        self.assertEqual(nov["days"][0]["date"], "2026-11-01")
        self.assertEqual(dec["days"][-1]["date"], "2026-12-31")
        self.assertEqual(dec["opening"], nov["closing"])
        for month in (nov, dec):
            self.assertEqual(round(month["opening"] + month["net"], 2), month["closing"])
        self.assertEqual(result["baseline"], result["scenario"])

    def test_scenario_changes_balance_and_one_occurrence_without_writes(self):
        self.payment()
        original = self.request()
        event = next(e for e in original["events"] if e["name"] == "Example bill")
        # Guard the actual projection: even temporary SQL writes would fail this test.
        fs.no_writes(self, AssertionError("Scenario attempted a write"))
        result = self.request(balances={"chk": 5500}, edits={event["key"]: -250})
        self.assertEqual(result["baseline"], original["baseline"])
        self.assertEqual(result["scenario"][0]["closing"] - original["baseline"][0]["closing"], 350)
        self.assertEqual(result["scenario"][1]["closing"] - original["baseline"][1]["closing"], 350)
        self.assertEqual(self.request(), original)
        self.assertEqual(self.conn.execute(select(Account.balance).where(Account.id == "chk")).scalar(), 5000)
        self.assertEqual(self.conn.execute(select(Recurring.amount)).scalar(), -100)
        self.assertEqual(self.conn.execute(select(Override)).fetchall(), [])

    def test_card_modes_reuse_statement_minimum_and_custom_cap(self):
        for mode, amount, expected in [("full", None, -800), ("minimum", None, -40),
                                        ("fixed", 125, -125), ("fixed", 2000, -800)]:
            with self.subTest(mode=mode, amount=amount):
                api_account_update(self.conn, {}, {"pay_mode": mode, "pay_amount": amount}, "cc")
                result = self.request()
                event = next(e for e in result["events"] if e["kind"] == "card")
                self.assertEqual(event["date"], "2026-11-05")
                self.assertEqual(event["amount"], expected)

    def test_income_weekend_and_payment_holiday_use_existing_settlement(self):
        api_recurring_add(self.conn, {}, {"name": "Example income", "account_id": "chk", "amount": 1000,
                                         "frequency": "once", "anchor_date": "2026-11-15", "active": 1})
        api_recurring_add(self.conn, {}, {"name": "Example payment", "account_id": "chk", "amount": -100,
                                         "frequency": "once", "anchor_date": "2026-11-11", "active": 1})
        events = {e["name"]: e for e in self.request()["events"]}
        self.assertEqual(events["Example income"]["date"], "2026-11-13")
        self.assertEqual(events["Example payment"]["date"], "2026-11-12")

    def test_manual_account_create_edit_and_connected_protection(self):
        result = api_family_account(self.conn, {}, {"name": "Example checking", "kind": "checking",
                                                    "balance": "1200.55", "balance_date": "2026-10-29"})
        aid = result["id"]
        self.assertTrue(result["ok"])
        api_family_account(self.conn, {}, {"id": aid, "balance": -50, "balance_date": "2026-10-29"})
        row = self.conn.execute(select(Account).where(Account.id == aid)).fetchone()
        self.assertEqual(row["balance"], -50)
        self.assertEqual(row["provider"], "manual")
        with self.assertRaisesRegex(ApiError, "Only manual"):
            api_family_account(self.conn, {}, {"id": "chk", "balance": 0, "balance_date": "2026-10-29"})
        with self.assertRaisesRegex(ApiError, "not found"):
            api_family_account(self.conn, {}, {"id": "missing", "balance": 0, "balance_date": "2026-10-29"})

    def test_invalid_scenarios_and_inputs(self):
        for kw in [{"start": "bad"}, {"start": "2026-11-02"}, {"account_id": "cc"},
                   {"balances": {"missing": 1}}, {"edits": {"rec:bad": -10}},
                   {"balances": {"chk": "nan"}}, {"balances": {"chk": True}}, {"edits": []}]:
            with self.subTest(kw=kw), self.assertRaises(ApiError):
                self.request(**kw)
        for value in ["nan", "inf", True, "", 10**20]:
            with self.subTest(value=value), self.assertRaises(ApiError):
                api_family_account(self.conn, {}, {"name": "Example", "balance": value,
                                                    "balance_date": "2026-10-29"})
        with self.assertRaisesRegex(ApiError, "future"):
            api_family_account(self.conn, {}, {"name": "Example", "balance": 1, "balance_date": "2099-01-01"})

    def test_existing_saved_overrides_stay_intact(self):
        self.payment()
        event = next(e for e in self.request()["events"] if e["name"] == "Example bill")
        self.conn.execute(insert(Override).values(key=event["key"], amount=-75))
        result = self.request(edits={event["key"]: -150})
        self.assertEqual(result["scenario"][0]["closing"] - result["baseline"][0]["closing"], -75)
        self.assertEqual(self.conn.execute(select(Override.amount)).scalar(), -75)

    def test_earlier_start_month_opening_and_zero_balance(self):
        result = self.request(start="2026-10-29", balances={"chk": 0})
        fc, _ = forecast.project(self.conn, date(2026, 10, 29), 63, balances={"chk": 0})
        self.assertEqual(result["scenario"][0]["opening"], fc["accounts"][0]["series"][2])

    def test_forecast_error_does_not_change_saved_balance(self):
        with mock.patch("runway.domain.forecast.project", side_effect=RuntimeError("Unavailable")):
            with self.assertRaises(RuntimeError):
                self.request(balances={"chk": 0})
        self.assertEqual(self.conn.execute(select(Account.balance).where(Account.id == "chk")).scalar(), 5000)

    def test_card_scenario_payment_recomputes_carryover_without_saving(self):
        original = self.request()
        event = next(e for e in original["events"] if e["kind"] == "card")
        fs.no_writes(self, AssertionError("Scenario attempted a write"))
        result = self.request(edits={event["key"]: 0})
        self.assertGreater(result["scenario"][0]["closing"], original["baseline"][0]["closing"])
        self.assertEqual(self.request(), original)
        with self.assertRaisesRegex(ApiError, "zero or negative"):
            self.request(edits={event["key"]: 50})
