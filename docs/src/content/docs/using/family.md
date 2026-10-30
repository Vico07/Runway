---
title: Family Finance Hub
description: Manual balances, scheduled payments, temporary scenarios and November/December 2026 checking cash flow.
sidebar:
  order: 2
---

Open **Family Finance Hub** in the navigation. It uses Runway’s existing accounts, recurring schedules, budgets, pending adjustments and credit card forecasting engine; no bank connection is required.

## Accounts and scheduled payments

Add a manual checking, savings or credit card account and enter its opening balance. Card debt is negative. Manual balances can be edited with an explicit balance date. Bank-connected balances remain controlled by sync. Add payments as negative amounts and income as positive amounts. Choose a one-time, weekly, biweekly or monthly schedule. **Edit existing scheduled payments** opens [Recurring](/Runway/using/recurring/) for changes, removal and the complete set of scheduling options.

For each card, select its paying account and **Minimum**, **Full statement** or **Custom amount**, then save. The existing [account settings](/Runway/using/settings/) editor accepts statement balances, closing/due dates, issuer minimums and APR. Custom payments are capped at the remaining statement. Missing issuer minimums use Runway’s estimated minimum; unpaid amounts and interest carry forward through the existing forecast. Warnings identify missing or stale statements. Saving a payment mode changes the baseline; a scenario changes nothing saved.

## Compare November and December 2026

Select a checking account included in the Overview forecast and a forecast start date on or before November 1, 2026. When several checking accounts exist, use Settings → Accounts to select the primary account or include accounts in the forecast.

The forecast assumes account balances are opening balances on the chosen start date, with Runway’s pending adjustments. It does **not** reconstruct historical balances from transactions or the balance date. Check balances against the chosen start date before interpreting the projection.

**Compare cash flow** shows November and December side by side: opening balance, income, outflow including budgets and card payments, net cash flow, closing balance, and the lowest daily balance and date. Expand **Daily checking balances** for each day. December continues from November’s closing balance; it does not reset to the entered balance. Transfers and card payments are cash movements, so outflow here is not a spending-category report.

## Temporary what-if scenarios

Enter an optional what-if opening balance, or choose a scheduled occurrence and preview a different signed amount (zero skips its projected amount). Changes affect only that occurrence, with Runway recomputing the forecast and card carryover where applicable. The two monthly panels compare baseline and what-if values. Multiple occurrence changes can be combined.

Scenarios live only on the open page. They never update account balances, scheduled items, saved forecast overrides or card settings, and disappear on reset, navigation or reload. A failed comparison clears the old result and displays an error. No scenario is automatically applied to the baseline.

## Preview with made-up data

From the repository, with Python 3.14, Poetry and Node 26 available:

```bash
make setup
make frontend-build
RUNWAY_DATA=/tmp/runway-family-preview poetry run python run.py demo
RUNWAY_DATA=/tmp/runway-family-preview poetry run python run.py --no-sync
```

Open the app on port 8765 and choose **Family Finance Hub** (route `#family`). Use a new empty preview directory to keep demo data separate from personal records. The demo data is relative to today; for the fixed November/December comparison, enter appropriate **made-up** card statements and scheduled payments. OIDC sign-in remains required when exposing Runway beyond localhost; see [deployment](/Runway/start/docker/).


## Household planning and Home Assistant

Open [Budget & Spending](/Runway/using/spending/) for category budgets, imports, trends, merchant drill-down and loan/transfer classification. [Smart Card Planner](/Runway/using/card-planner/) compares manually verified card terms and hypothetical purchases. Both are links in the Hub and use the existing account, transaction and forecast data. [Home Assistant installation](/Runway/start/home-assistant/) opens the same application through authenticated Ingress. Pinch-to-zoom is enabled on mobile.
