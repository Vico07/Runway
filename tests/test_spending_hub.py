"""Split-aware household consumption, cash transfers, debt allocation, and manual CSV imports."""
from sqlalchemy import insert, select

from runway.domain import categories, splits
from runway.server.api.spending import api_spending, api_spending_classify, api_spending_import
from runway.server.common import ApiError
from runway.storage.models import Budget, Recurring, Transaction
from tests.shared import LedgerCase, freeze_today


class SpendingTests(LedgerCase):
    def setUp(self):
        super().setUp()
        freeze_today(self)
        self.acct("chk", "checking", 5000, provider="manual")
        self.acct("cc", "credit", -100, pay_from="chk", provider="manual")

    def summary(self, **q):
        return api_spending(self.conn, {"month": ["2026-09"], **{k: [v] for k, v in q.items()}}, {})["data"]

    def test_card_purchase_is_expense_but_both_sides_of_repayment_are_not(self):
        self.tx("cc", "2026-09-12", -100, "Example market", "Groceries")
        self.tx("chk", "2026-09-15", -100, "Example card payment", "Credit Card Payment")
        self.tx("cc", "2026-09-15", 100, "Example card payment", "Credit Card Payment")
        self.tx("chk", "2026-09-15", -50, "Example savings", "Transfer")
        result = self.summary()
        self.assertEqual(result["spent"], 100)
        self.assertEqual(result["categories"][next(i for i,r in enumerate(result["categories"]) if r["name"] == "Groceries")]["spent"], 100)
        self.assertEqual(result["non_consumption"], 50)
        self.assertEqual(self.summary(account="cc")["spent"], 100)
        self.assertEqual(self.summary(account="chk")["spent"], 0)

    def test_loan_payment_is_unallocated_until_split_into_actual_principal_and_interest(self):
        self.tx("chk", "2026-09-02", -500, "Example lender", "Mortgage")
        result = self.summary()
        self.assertEqual(result["spent"], 0)
        self.assertEqual(result["unallocated_debt"], 500)
        api_spending_classify(self.conn, {}, {"data": {"category": "Mortgage Principal", "classification": "principal"}})
        api_spending_classify(self.conn, {}, {"data": {"category": "Mortgage Interest", "classification": "interest"}})
        tx = self.conn.execute(select(Transaction.id)).scalar()
        splits.set_splits(self.conn, tx, [{"category": "Mortgage Principal", "amount": -400}, {"category": "Mortgage Interest", "amount": -100}])
        result = self.summary()
        self.assertEqual(result["spent"], 100)
        self.assertEqual(result["unallocated_debt"], 0)
        self.assertEqual(result["non_consumption"], 400)
        self.assertTrue(next(c for c in categories.all_categories(self.conn) if c["name"] == "Mortgage Principal")["is_transfer"])

    def test_budget_thresholds_refunds_and_prior_comparable_days(self):
        self.conn.execute(insert(Budget).values(category="Groceries", amount=100))
        self.tx("cc", "2026-09-05", -90, "Example market", "Groceries")
        self.tx("cc", "2026-09-07", 5, "Example refund", "Groceries")
        self.tx("cc", "2026-08-05", -70, "Example market", "Groceries")
        self.tx("cc", "2026-08-30", -200, "Example later", "Groceries")
        result = self.summary()
        grocery = next(r for r in result["categories"] if r["name"] == "Groceries")
        self.assertEqual((grocery["spent"], grocery["remaining"], grocery["warning"]), (85, 15, "near"))
        self.assertEqual(result["prior_comparable"], 70)
        self.assertEqual(sum(r["spent"] for r in result["weekly"]), 85)

    def test_csv_quoted_descriptions_duplicate_detection_and_row_errors(self):
        raw = 'date,amount,description,merchant,category\n2026-09-02,-12.50,"ORIGINAL, STORE",Example shop,Shopping\n2026-09-03,bad,INVALID,Example shop,Shopping\n'
        result = api_spending_import(self.conn, {}, {"data": {"account": "cc", "csv": raw}})["data"]
        self.assertEqual((result["added"], result["skipped"]), (1, 1))
        self.assertEqual(self.conn.execute(select(Transaction.description)).scalar(), "ORIGINAL, STORE")
        self.assertEqual(result["rows"][1]["status"], "error")
        again = api_spending_import(self.conn, {}, {"data": {"account": "cc", "csv": raw}})["data"]
        self.assertEqual(again["added"], 0)
        self.assertEqual(again["rows"][0]["status"], "duplicate")
        self.assertEqual(self.summary()["spent"], 12.50)

    def test_missing_coverage_and_uncategorized_data_are_not_claimed_verified(self):
        self.tx("cc", "2026-09-02", -30, "Example uncategorized")
        result = self.summary()
        self.assertFalse(result["reconciled"])
        self.assertEqual(result["uncategorized"], 1)
        self.assertEqual(result["spent"], 0)
        self.assertEqual(result["unclassified_outflow"], 30)
        self.assertTrue(result["missing_accounts"])
        self.assertTrue(result["warnings"])

    def test_confirmed_subscriptions_are_monthly_schedules_not_invented_spending(self):
        self.conn.execute(insert(Recurring).values(name="Example subscription", account_id="cc", amount=-10,
                                                  frequency="monthly", anchor_date="2026-09-01", category="Subscriptions", active=1))
        result = self.summary()
        self.assertEqual(result["subscriptions"][0]["monthly_estimate"], 10)
        self.assertEqual(result["spent"], 0)

    def test_invalid_csv_and_transfer_reclassification_are_refused(self):
        for csv in ("wrong,headers\n1,2", "date,amount,description\n1,2,3,4"):
            with self.assertRaises(ApiError):
                api_spending_import(self.conn, {}, {"data": {"account": "cc", "csv": csv}})
        with self.assertRaises(ApiError):
            api_spending_classify(self.conn, {}, {"data": {"category": "Transfer", "classification": "variable"}})
