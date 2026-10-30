<script lang="ts">
  import type { SpendingSummary } from "$lib/family-types";
  import { onMount } from "svelte";
  import { apiCall } from "$lib/contract";
  import { errMsg } from "$lib/act";
  import { fmt, thisMonth } from "$lib/format";
  import { showTransactions } from "$lib/filters.svelte";
  import BudgetView from "$lib/components/budget/BudgetView.svelte";
  import Trends from "$lib/components/reports/Trends.svelte";
  import Merchants from "$lib/components/reports/Merchants.svelte";
  import RecurringView from "$lib/components/recurring/RecurringView.svelte";
  import SubTabs from "$lib/components/SubTabs.svelte";
  import { Button } from "$lib/components/ui/button";
  import { Input } from "$lib/components/ui/input";
  import * as Card from "$lib/components/ui/card";
  let { sub = "overview" }: { page?: string; sub?: string } = $props();
  const tabs = ["overview", "targets", "trends", "merchants", "subscriptions", "import"];
  let month = $state(thisMonth());
  let account = $state("");
  let category = $state("");
  let data = $state<SpendingSummary | null>(null);
  let error = $state("");
  let status = $state("");
  let busy = $state(false);
  let csv = $state("");
  let importAccount = $state("");
  let categoryName = $state("");
  let classification = $state("variable");
  const field = "h-11 w-full rounded-md border bg-background px-3 focus-visible:outline-2 focus-visible:outline-ring";
  async function load() {
    busy = true; error = ""; data = null;
    try {
      data = (await apiCall<"GET /api/spending">(`/api/spending?${new URLSearchParams({ month, account, category })}`)).data as unknown as SpendingSummary;
      importAccount ||= data.accounts[0]?.id ?? "";
    } catch(e) { error = errMsg(e); } finally { busy = false; }
  }
  async function classify() {
    busy = true; error = "";
    try { await apiCall<"POST /api/spending/classify">("/api/spending/classify", {method:"POST",body:{data:{category:categoryName,classification}}}); await load(); }
    catch(e) { error = errMsg(e); } finally { busy = false; }
  }
  async function importCsv() {
    busy = true; error = ""; status = "";
    try {
      const r = (await apiCall<"POST /api/spending/import">("/api/spending/import", {method:"POST",body:{data:{account:importAccount,csv}}})).data as {rows:{status:string;i:number;error?:string}[];added:number;skipped:number};
      const failed = r.rows.filter((row: {status:string}) => row.status === "error");
      status = `${r.added} added; ${r.skipped} skipped (duplicates or errors). ${failed.map((row: {i:number;error?:string}) => `Row ${row.i + 2}: ${row.error}`).join(" ")}`;
      await load();
    } catch(e) { error = errMsg(e); } finally { busy = false; }
  }
  onMount(load);
</script>
<div class="space-y-5">
  <header><h1 class="text-2xl font-semibold">Budget &amp; Spending</h1><p class="mt-2 text-muted-foreground">Where household money goes across checking and credit cards. Card repayments and transfers are excluded from consumption.</p></header>
  <SubTabs class="[&_a]:min-h-11" label="Budget & Spending" current={sub || "overview"} tabs={tabs.map(id => ({id, label: id === "targets" ? "Budget targets" : id[0].toUpperCase()+id.slice(1),href:`#spending/${id}`}))} />
  <div class="flex flex-wrap gap-3"><Button class="min-h-11" href="#transactions" variant="outline">Transactions, search and splits</Button><Button class="min-h-11" href="#setup/categories" variant="outline">Categories and persistent rules</Button><Button class="min-h-11" href="#cardplanner" variant="outline">Smart Card Planner</Button></div>
  {#if error}<p role="alert" class="rounded border border-destructive p-3">{error}</p><Button class="min-h-11" onclick={load}>Retry</Button>{/if}
  {#if status}<p role="status">{status}</p>{/if}
  {#if busy}<p role="status">Loading…</p>{/if}
  {#if sub === "targets"}<BudgetView />
  {:else if sub === "trends"}<Trends />
  {:else if sub === "merchants"}<Merchants />
  {:else if sub === "subscriptions"}
    {#if data}<Card.Root><Card.Header><Card.Title>Subscription overview · {data.month}</Card.Title><Card.Description>Confirmed schedules in the Subscriptions category. Recurring candidates below require review before they become schedules.</Card.Description></Card.Header><Card.Content>{#each data.subscriptions as item (item.id)}<p>{item.name} · {fmt(item.monthly_estimate)} scheduled this month · {item.frequency}</p>{:else}<p>No categorized subscription schedules. Review recurring candidates or add a subscription below.</p>{/each}</Card.Content></Card.Root>{/if}
    <RecurringView />
  {:else if sub === "import"}
    <Card.Root><Card.Header><Card.Title>Import a CSV statement</Card.Title><Card.Description>Required headers: date,amount,description. Optional: merchant,category. Dates YYYY-MM-DD; signed amounts (negative purchases, positive income/refunds). At most 500 rows. Imports do not overwrite balances or reconcile a statement. Review repayment classifications after import.</Card.Description></Card.Header><Card.Content>
      <form onsubmit={e=>{e.preventDefault();void importCsv();}} class="space-y-4">
        <label class="block">Account<select aria-label="Account" class={field} required bind:value={importAccount}><option value="" disabled>Choose an account</option>{#each data?.accounts ?? [] as a (a.id)}<option value={a.id}>{a.name}</option>{/each}</select></label>
        <label class="block">CSV file<Input class="min-h-11" type="file" accept=".csv,text/csv" onchange={async e=>{const f=e.currentTarget.files?.[0]; if(f) {if(f.size>500_000) error="CSV must be under 500 KB";else csv=await f.text();}}} /></label>
        <label class="block">CSV contents<textarea class={`${field} min-h-40 py-3`} required bind:value={csv}></textarea></label>
        <Button class="min-h-11" type="submit" disabled={busy || !importAccount}>Import transactions</Button>
      </form>
      <p class="mt-4 text-sm">Use Transactions → Add transaction for individual entries. Imported original descriptions are preserved; duplicate rows are skipped by the existing importer. Row errors are reported individually.</p>
    </Card.Content></Card.Root>
  {:else}
    <form class="grid items-end gap-3 sm:grid-cols-4" onsubmit={e=>{e.preventDefault();void load();}}>
      <label>Month<Input class="min-h-11" type="month" required bind:value={month} /></label>
      <label>Account or card<select aria-label="Account or card" class={field} bind:value={account}><option value="">All covered accounts</option>{#each data?.accounts ?? [] as a (a.id)}<option value={a.id}>{a.name}</option>{/each}</select></label>
      <label>Category filter<Input class="min-h-11" bind:value={category} placeholder="All categories" /></label>
      <Button class="min-h-11" type="submit" disabled={busy}>Apply filters</Button>
    </form>
    {#if data}
      <div class="grid gap-3 sm:grid-cols-3">{#each [["Consumption",data.spent],["Fixed and interest",data.fixed],["Variable",data.variable],["Prior comparable days",data.prior_comparable],["Remaining month estimate",data.remaining_estimate],["Unallocated debt payments",data.unallocated_debt],["Uncategorized outflows (not yet consumption)",data.unclassified_outflow]] as item (item[0])}<Card.Root><Card.Header><Card.Description>{item[0]}</Card.Description><Card.Title>{fmt(Number(item[1]))}</Card.Title></Card.Header></Card.Root>{/each}</div>
      <p class="text-sm text-muted-foreground">{data.estimate_method} Prior comparison uses the same elapsed days. Budget targets below cover the whole selected month; account filters narrow actuals, not household targets.</p>
      <section aria-label="Data quality" class="space-y-2 rounded border p-4"><h2 class="font-semibold">Freshness, coverage and reconciliation</h2>{#each data.warnings as warning (warning)}<p>{warning}</p>{/each}<p>{data.uncategorized} uncategorized transactions · No external reconciliation verified</p><details><summary class="min-h-11 cursor-pointer py-3">Account coverage and balance dates</summary>{#each data.last_dates as a, i (i)}<p>{a.name} · {a.balance_date || "No balance date"}{a.hidden ? " · excluded" : ""}</p>{/each}</details></section>
      <Card.Root><Card.Header><Card.Title>Monthly budget vs actual</Card.Title><Card.Description>Choose a category to open its transactions, with merchant, date, amount, account and original description. Configure detailed category targets in Budget targets.</Card.Description></Card.Header><Card.Content class="overflow-x-auto"><table class="w-full text-sm"><thead><tr><th class="p-2 text-left">Category</th><th class="p-2">Spent</th><th class="p-2">Target</th><th class="p-2">Remaining</th><th class="p-2">Status</th></tr></thead><tbody>{#each data.categories as r (r.name)}<tr><td><Button class="min-h-11" variant="link" onclick={()=>showTransactions({month,category:r.name,account})}>{r.name}</Button></td><td class="p-2 text-right">{fmt(r.spent)}</td><td class="p-2 text-right">{r.budget == null ? "Not set" : fmt(r.budget)}</td><td class="p-2 text-right">{r.remaining == null ? "—" : fmt(r.remaining)}</td><td class="p-2" class:text-destructive={r.warning === "over"}>{r.warning === "over" ? "Over budget" : r.warning === "near" ? "Approaching budget" : ""}</td></tr>{/each}</tbody></table></Card.Content></Card.Root>
      <div class="grid gap-4 lg:grid-cols-2">
        <Card.Root><Card.Header><Card.Title>Merchant rankings</Card.Title></Card.Header><Card.Content>{#each data.merchants as r (r.name)}<div class="flex items-center justify-between gap-2"><Button class="min-h-11" variant="link" onclick={()=>showTransactions({month,account,q:r.name,category})}>{r.name}</Button><span>{fmt(r.spent)}</span></div>{:else}<p>No imported spending for this selection.</p>{/each}</Card.Content></Card.Root>
        <Card.Root><Card.Header><Card.Title>Weekly and monthly trends</Card.Title><Card.Description>Weeks start Monday and are clipped to the selected month. Current month may be partial.</Card.Description></Card.Header><Card.Content>{#each data.weekly as r (r.week)}<p>Week {r.week}: {fmt(r.spent)}</p>{/each}<hr class="my-3" />{#each data.monthly as r (r.month)}<p>{r.month}: {fmt(r.spent)}</p>{/each}</Card.Content></Card.Root>
      </div>
      <Card.Root><Card.Header><Card.Title>Expense classification</Card.Title><Card.Description>Separate principal and transfers from consumption. Use the lender's actual principal/interest split in Transactions. No automatic loan allocation is guessed. Marking an existing category as principal or transfer moves it under Transfer in all reports.</Card.Description></Card.Header><Card.Content><form class="grid items-end gap-3 sm:grid-cols-3" onsubmit={e=>{e.preventDefault();void classify();}}><label>Category name<Input class="min-h-11" required bind:value={categoryName} placeholder="Mortgage Principal" /></label><label>Classification<select aria-label="Classification" class={field} bind:value={classification}>{#each ["variable","fixed","principal","interest","transfer","unallocated_debt"] as c (c)}<option value={c}>{c.replaceAll("_"," ")}</option>{/each}</select></label><Button class="min-h-11" type="submit" disabled={busy}>Save classification</Button></form></Card.Content></Card.Root>
      <details><summary class="min-h-11 cursor-pointer py-3">Imported transaction details (first 500)</summary><div class="overflow-x-auto"><table class="w-full text-sm"><thead><tr><th>Merchant</th><th>Date</th><th>Amount</th><th>Account</th><th>Original description</th></tr></thead><tbody>{#each data.transactions as t, i (`${t.id}:${i}`)}<tr><td class="p-2">{t.payee || t.description}</td><td class="p-2">{t.posted}</td><td class="p-2">{fmt(t.amount)}</td><td class="p-2">{t.account_name}</td><td class="p-2">{t.description || "Not supplied"}</td></tr>{/each}</tbody></table></div></details>
    {/if}
  {/if}
</div>
