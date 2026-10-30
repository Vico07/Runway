---
title: Smart Card Planner
description: Verified card terms, hypothetical purchases, rewards and cash-flow safety.
sidebar:
  order: 4
---

Open **Smart Card Planner** (`#cardplanner`). It reuses the existing accounts, manual statements, category budgets, recurring schedules and daily cash-flow engine. It is not a new ledger and does not enable bank sync. Add your card accounts in Family Finance Hub and choose the checking account that pays each card. Any card can be profiled; no Apple, Prime Visa, IHG, AAdvantage, Best Buy, Sam's Club or other issuer benefits are prefilled or assumed.

## Verify card profiles

Enter credit limit, available credit, purchase APR, optional foreign transaction fee, statement closing/payment due days, grace status (active/lost/unknown), whether a balance carries interest, verification date and source. Enter actual last-close date, actual due date, statement balance and minimum together to use Runway's existing manual statement store. Account balances remain in the Hub. Fresh manually verified cycle days clarify month-end statements, including a day-31 cycle closing in February.

A profile is eligible for recommendations only with sourced terms verified in the past **30 days**, known critical fields and a current statement. Recorded card and checking balances also need as-of dates within **seven days** before the reserve check is trusted. These are manual verification declarations, not a claim of independent bank confirmation. Unknown fields stay unknown. Check issuer terms again before acting.

Rewards use editable JSON terms. Example structure (synthetic, not any real card benefit):

```json
[{"unit":"USD","rate":0,"merchant":null,"category":null,"starts":null,"expires":null,"cap":null,"used":0}]
```

For USD cashback, `rate` is a percentage. Other units, such as points or miles, use units per dollar; an optional `value` is **dollars per unit**, explicitly chosen by you. There is no universal airline/hotel valuation. Terms may be merchant/category specific, date limited and capped in eligible dollars; `used` is manually verified eligible spending already against the cap. Terms are not stacked. The best applicable *priced* term is used; no applicable verified term leaves the valuation unknown. Use an explicitly verified zero-rate term for a no-rewards card. Caps/usage do not update from the issuer automatically.

Restrictions JSON accepts `excluded_merchants`, `excluded_categories` and `domestic_only`. Promotional fields include introductory/deferred type, APR, effective dates, eligible minimum, existing promotional balance and a payoff plan date. Mark promotions verified only after checking eligibility and issuer rules. Mixed standard/promotional balances are not safely optimized by a single APR model and are not ranked as a promotional recommendation. Missing/expired promotion terms or an unsafe deferred-interest deadline block recommendations.

## Compare a purchase and timing

Enter amount, merchant/category, proposed date, one-time/monthly frequency, checking account, reserve and repayment strategy. You may choose a preferred card and whether to avoid interest-bearing balances, use a verified promotion or include a foreign transaction fee. Change the date and compare again to simulate another statement cycle. The date and amount remain hypothetical until saved.

The result shows native reward units and their explicitly valued dollar estimate, purchase interest/fees, estimated net purchase cost, expected close/due dates, utilization, checking low before/after, daily balances and future payment events. Debit is compared separately as spending from checking. The budget comparison shows actual, proposed spending and remaining target; estimated rewards are never shown as actually earned rewards.

The engine follows Runway's business-day settlement for schedules. A proposed weekend/holiday purchase is modeled on the next business day, with a warning. If this crosses a statement close, issuer posting must be verified before ranking it. Closing-day purchases are uncertain too. **Delaying a purchase never guarantees an interest-free period.** Grace status and posting rules still matter.

Options must clear credit limits/available credit, interest-bearing-balance preferences, current statements, reserve and forecast warnings, promotions and applicable rule conditions before ranking. Eligible options are ordered by avoiding interest/fees first, then verified net cost, with preference only as a final tie-breaker. Unknown/stale APR, grace, rewards valuations or dates prompt verification rather than a fabricated winning card. USD comparisons do not invent FX rates.

Interest is a simple purchase-level estimate over the specified horizon, not an issuer payoff quote or full amortization of every balance. Full-statement repayment with verified active grace may have zero purchase interest. Lost grace can accrue interest from purchase. Minimum/fixed/custom payments without a payoff horizon have **unknown total borrowing cost** and are not ranked as a known-cost option. Ongoing monthly purchases require a full-statement plan for a bounded comparison. Existing balance interest continues through Runway's native forecast.

## Repayment and saving

Choose existing strategy, full statement, minimum, fixed, custom, or a target payoff date. Minimum/fixed/custom need a target horizon for cost comparison. A date alone does not establish payoff: if the native projection leaves a statement unpaid at the target, the option is not ranked and borrowing cost remains unknown. A target strategy calculates a conservative fixed installment using the card balance, proposed purchase, APR and payment opportunities; it is an **estimate**, not a guaranteed payoff schedule. Targets before the first possible payment require an additional issuer payment and are not represented as automatically satisfied. Verify final payoff, residual interest and any promotional deadline yourself.

**Save planned purchase** explicitly creates a native Recurring charge on the selected card and stores plan metadata. It does not create an actual purchase transaction or deduct checking immediately. Saving a changed repayment strategy also changes that card's **whole-account** payment strategy, since an issuer statement combines its purchases. The UI calls this out before saving. The core forecast sizes and caps statement payments and carries unpaid balances forward; repayments remain transfers rather than additional consumption.

Edit saved schedules in Recurring. The Planner flags when their date/amount differs from the saved plan metadata. Cancel deactivates the future schedule without deleting actual transactions. It leaves the card’s saved whole-account repayment strategy in place; edit that strategy in Family Finance Hub if needed. After a real purchase posts, import/enter it and match the schedule in the existing transaction/Recurring tools; a plan is not proof that an issuer charge happened. Budgets may already allow for a proposed charge, so incremental checking impact can be smaller than its price. There is no assertion that a target or the reserve will hold when records, schedules or unbudgeted spending are incomplete.

Preference rules can match merchant/category and require active grace, a balance ceiling, remaining available credit, a verified active promotion, enough category bonus cap and a checking reserve. Editing the same merchant/category replaces its rule; removal is explicit. Rules never override safety. A previously preferred but unsuitable card is flagged.

This supports comparing debit vs credit groceries, different cards for a merchant, a verified financing offer vs full payment, a later statement cycle, avoiding lost-grace cards and preserving a reserve while paying interest-bearing balances. All examples are scenarios, not assertions about a household's real cards or spending.

## Existing reward tools and example comparisons

**Recorded reward balances** opens Runway's existing Cards/Churning tools. Enter an issuer-confirmed points/cashback balance with its actual as-of date there. Native transaction-derived earnings and sign-up-bonus projections are estimates, not confirmed reward postings. The Planner does not turn a hypothetical purchase into earned rewards. Its verified profile terms are separate from the native best-card heuristics, which can use general issuer defaults; unverified defaults are deliberately not accepted for this planner's cost ranking.

Try these comparisons using your own verified profiles and hypothetical purchase details; none saves until **Save planned purchase**:

1. Groceries: select Groceries and compare the debit checking low with each full-statement card option.
2. Amazon: verify merchant-specific terms on Prime Visa and Apple Card, enter Amazon as merchant, and compare net costs and reserve effects. Neither card has assumed benefits.
3. Electronics: verify the Best Buy financing offer, its type and deadline; compare a target-date promotion scenario with a full-statement scenario. An expired or mixed-balance offer is not ranked confidently.
4. Statement timing: compare the same purchase before and after its verified closing day. Review close, due, monthly category budget and daily checking balances; actual issuer posting near close remains uncertain.
5. Lost grace: set the affected card's verified grace status to lost and compare with **Avoid cards carrying interest-bearing balances** enabled. Verify the warning rather than chasing its reward rate.
6. Existing high-interest debt: compare full/custom/target strategies and reserve levels using the recorded balance and APR. Inspect future obligations in the daily projection; the target installment is an estimate, and a final issuer payoff quote is still needed.
