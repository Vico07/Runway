---
title: Budget & Spending
description: Household consumption, category budgets, statement imports and reconciliation warnings.
sidebar:
  order: 3
---

Open **Budget & Spending** (`#spending`) from Runway's navigation or Family Finance Hub. The same responsive application works on desktop, iPhone and Home Assistant Ingress. It starts with your actual imported/manual transactions; no example household history is substituted.

## Existing Runway tools, reused

Runway already supplies category budgets and monthly overrides, split-aware reporting, merchant rankings and filters, transaction search, manual categorization and merchant renaming, persistent categorization rules, recurring detection, schedule matching and transaction editing. The tabs and links in this section reuse those screens, APIs and database tables. The transaction tools preserve original descriptions when a merchant is renamed.

**Budget targets** edits the native budgets. **Trends** and **Merchants** reuse existing reports, including account/card, category and date filters. Category and merchant links open the complete transaction list with those filters. **Transactions, search and splits** opens the existing editor; **Categories and persistent rules** opens the native Settings editor. There is no parallel transaction ledger.

Manual accounts now unlock budget/report/transaction tools without requiring a bank connection. The connected-bank indicator remains accurate; it is not set merely because a manual account exists.

## New household overview

Select a month, account/card and optional category. The overview shows consumption, fixed/interest and variable expenses, a comparable prior-period total, weekly and monthly trends, merchant rankings and category budget warnings at 80% and over 100%. Current periods can be partial. The comparable prior period uses the same elapsed days; full historical monthly totals remain available in Trends.

Budget targets are household targets even when actuals are filtered to one account. The top-category table avoids counting both a parent and its subcategories in its total. Use the native Budget editor for detailed child-category targets and rollover. Imported transaction details show merchant, date, signed amount, account and original description; the native list supports the full drill-down and search.

The remaining-month figure is **an estimate**, using known fixed schedules and the greater of known variable schedules or the variable spending pace to date (rather than adding the same planned expense twice), not a guarantee of what will be spent or an amount safe to spend. Smart Card Planner separately estimates the checking reserve until a scheduled paycheck. Recurring and credit card forecasts reuse the existing cash-flow engine.

Choose categories appropriate to your records. Existing categories include Groceries, Restaurants, Shopping, Utilities, Auto & Gas, Subscriptions, Home Improvement, Extra-Curriculars and Entertainment. Create categories such as Amazon, Transport, Kids or Home Maintenance with the native editor or classification form if desired; native rules can map a merchant to them. Merchant and category are distinct concepts: an Amazon order may contain several categories and should be split where appropriate.

## Consumption, repayments and loan allocation

A card purchase counts once, under its purchase category. **Credit Card Payment**, **Transfer**, and their transfer subcategories do not count as consumption: checking's outgoing repayment and the card's incoming repayment are not new expenses. Refunds lower spending under the same rules as native Runway reports.

Use **Expense classification** to create or classify categories as fixed, variable, interest, principal, transfer or unallocated debt. A principal/transfer category is placed under the native Transfer category so *all* Runway budget/report calculations exclude it from consumption. Marking an existing category as principal/transfer deliberately moves that category; review its transactions first. Existing transfer categories cannot silently become consumption through this form.

Unsplit **Mortgage** and **Loans** outflows appear separately as **unallocated debt payments**, with a reconciliation warning, rather than being asserted to be ordinary consumption. Split each lender payment using its **actual statement allocation**, for example Mortgage Principal + Mortgage Interest, or Car Loan Principal + interest. Principal is debt reduction; interest is a cost. Never infer the allocation from the checking withdrawal. Native older report screens retain their category-based behavior until you classify/split those records; the overview explicitly identifies the unresolved amount.

## CSV and manual entry

Use Transactions → Add transaction for individual manual entries. Import supports at most 500 rows / 500 KB per request. Select the actual account and provide a CSV file or paste its contents:

```csv
date,amount,description,merchant,category
2026-09-01,-12.50,"SYNTHETIC EXAMPLE, NOT HOUSEHOLD DATA",Example merchant,Shopping
```

Required headers are `date,amount,description`; `merchant` and `category` are optional. Dates use YYYY-MM-DD and amounts are signed: negative purchases, positive income/refunds. Quoted commas and a UTF-8 BOM are supported. Merchant can differ from the original description, which is preserved. Unknown categories and bad rows produce row-level errors; valid rows may still be imported, so inspect the returned added/skipped/error counts. Duplicates are skipped by the existing native importer. Re-import does not replace previous transactions or edit balances.

After import, categorize credit card repayments and savings transfers, split debt principal/interest, review uncategorized rows, match actual payments to schedules in Recurring and reconcile against the original statement. A CSV import alone does not establish that history is complete or a balance is verified.

## Subscriptions and data quality

**Subscriptions** lists active recurring schedules assigned to the Subscriptions category and their scheduled amount in the chosen month. The native recurring detector also identifies possible repeating payments from imported history; review and approve a candidate before calling it a subscription. Estimates and planned purchases never become actual spending automatically.

Uncategorized outflows are shown separately from consumption until reviewed: a withdrawal might be a transfer or card repayment, so it is not confidently counted twice. Native older report/budget screens retain their provisional handling of uncategorized spending.

The overview flags uncategorized transactions, missing account coverage, excluded hidden accounts, old/missing balance dates, pending transactions and unsplit loan payments. It always distinguishes recorded data from confirmed reconciliation; no external statement verification is invented. Accounts with no transactions might genuinely have no activity or might be missing history. Hidden accounts are intentionally excluded but can make household coverage incomplete.

In Home Assistant the sidebar opens the full application; read-only sensors are optional. No TV dashboard or duplicated Lovelace budgeting UI is included. See [Home Assistant installation](/Runway/start/home-assistant/) and [Smart Card Planner](/Runway/using/card-planner/).
