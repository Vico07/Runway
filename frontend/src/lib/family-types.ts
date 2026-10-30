/** Read models for the manual finance extensions; original native models remain unchanged. */
export interface FinanceAccount { id: string; name: string; display_name?: string | null; balance: number }
export interface SpendingSummary {
  month: string; spent: number; fixed: number; variable: number; prior_comparable: number;
  remaining_estimate: number; unallocated_debt: number; unclassified_outflow: number;
  estimate_method: string; warnings: string[]; uncategorized: number;
  accounts: FinanceAccount[];
  last_dates: {name: string; balance_date: string | null; hidden: boolean}[];
  subscriptions: {id: number; name: string; monthly_estimate: number; frequency: string}[];
  categories: {name: string; spent: number; budget: number | null; remaining: number | null; warning: string}[];
  merchants: {name: string; spent: number}[];
  weekly: {week: string; spent: number}[]; monthly: {month: string; spent: number}[];
  transactions: {id: number; posted: string; amount: number; account_name: string; payee: string | null; description: string; original_description?: string | null}[];
}
export interface CardProfile {
  credit_limit?: number; available_credit?: number; purchase_apr?: number; foreign_fee?: number;
  statement_balance?: number; minimum_payment?: number; promotional_apr?: number; promo_balance?: number;
  promo_minimum?: number; balance_threshold?: number; closing_day?: number; due_day?: number;
  last_close?: string; next_due?: string; verified_on?: string; promo_starts?: string;
  promo_expires?: string; promo_payoff_date?: string; grace: string; promo_type: string; source?: string;
  carrying_interest?: boolean; rewards_verified?: boolean; promo_verified?: boolean;
  rewards?: unknown[]; restrictions?: Record<string, unknown>;
}
export interface CardRule {
  merchant?: string; category?: string; card_id: string; require_grace: boolean;
  require_promotion: boolean; require_cap: boolean; max_balance?: number; min_available?: number; reserve?: number;
}
export interface PlannerData {
  cards: FinanceAccount[]; checking: FinanceAccount[]; profiles: Record<string, CardProfile>; rules: CardRule[];
  purchases: {id: string; date: string; merchant: string; amount: number; status: string; schedule_changed: boolean}[];
}
interface Low {balance: number; date: string}
export interface CardQuote {
  recommendation: string | null; explanation: string; notice: string; safe_to_spend_until_paycheck: number | null;
  debit: {net_cost: number; low: Low; reserve_protected: boolean};
  budget: {actual: number; planned: number; remaining_after: number | null};
  options: {card_id: string; name: string; eligible: boolean; reasons: string[]; warnings: string[];
    close: string | null; due: string | null; rewards: {units: number; unit: string; dollars: number | null};
    interest_estimate: number | null; fees: number; net_cost: number | null; utilization: number | null;
    deferred_interest_risk: number | null;
    cashflow: {before_low: Low; after_low: Low; payment_events: {key: string; date: string; amount: number}[]; days: string[]; balances: number[]} | null;
  }[];
}
