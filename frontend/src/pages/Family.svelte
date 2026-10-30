<script lang="ts">
  import { onMount } from "svelte";
  import { refreshState } from "$lib/app.svelte";
  import { basePath } from "$lib/path";
  import { api } from "$lib/api";
  import { apiCall } from "$lib/contract";
  import type { AccountItem, FamilyForecastReply } from "$lib/api-types";
  import { ACCOUNT_KINDS, KIND_LABEL } from "$lib/accounts";
  import { errMsg } from "$lib/act";
  import { fmt, isoDay } from "$lib/format";
  import { Button } from "$lib/components/ui/button";
  import { Input } from "$lib/components/ui/input";
  import * as Card from "$lib/components/ui/card";

  let accounts = $state<AccountItem[]>([]);
  let accountId = $state("");
  let start = $state("2026-11-01");
  let result = $state<FamilyForecastReply | null>(null);
  let error = $state("");
  let status = $state("");
  let busy = $state(false);
  let ready = $state(false);
  let balances = $state<Record<string, string>>({});
  let balanceDates = $state<Record<string, string>>({});
  let scenarioBalance = $state("");
  let edits = $state<Record<string, string>>({});
  let eventKey = $state("");
  let eventAmount = $state("");
  let accountName = $state("");
  let accountKind = $state("checking");
  let newBalance = $state("");
  let paymentName = $state("");
  let paymentAmount = $state("");
  let paymentDate = $state("2026-11-02");
  let frequency = $state("monthly");
  let paymentAccount = $state("");
  let modes = $state<Record<string, string>>({});
  let custom = $state<Record<string, string>>({});
  let payers = $state<Record<string, string>>({});
  const checking = $derived(accounts.filter(a => a.kind === "checking" && !a.hidden));
  const cash = $derived(accounts.filter(a => (a.kind === "checking" || a.kind === "savings") && !a.hidden));
  const cards = $derived(accounts.filter(a => a.kind === "credit" && !a.hidden));
  const selectClass = "h-11 w-full rounded-md border bg-background px-3 text-sm focus-visible:outline-2 focus-visible:outline-ring";

  async function load() {
    ready = false;
    accounts = await apiCall<"GET /api/accounts">("/api/accounts");
    for (const a of accounts) {
      balances[a.id] = String(a.balance ?? 0);
      balanceDates[a.id] = a.balance_date?.slice(0, 10) ?? isoDay();
      modes[a.id] = a.pay_mode ?? "full";
      custom[a.id] = a.pay_amount == null ? "" : String(a.pay_amount);
      payers[a.id] = a.pay_from ?? "";
    }
    if (!accounts.some(a => a.id === accountId)) accountId = checking[0]?.id ?? "";
    paymentAccount ||= accountId;
    ready = true;
  }
  async function action(work: () => Promise<void>, message = "") {
    busy = true; error = ""; status = "";
    try { await work(); status = message; }
    catch (e) { error = errMsg(e); }
    finally { busy = false; }
  }
  function invalidate() { result = null; }
  async function compare() {
    result = null;
    await action(async () => {
      result = await apiCall<"POST /api/family/forecast">("/api/family/forecast", { method: "POST", body: {
        start, account_id: accountId, balances: scenarioBalance === "" ? {} : { [accountId]: scenarioBalance }, edits,
      } });
    });
  }
  async function saved(work: () => Promise<unknown>) {
    invalidate();
    await action(async () => { await work(); await load(); await refreshState(); }, "Saved. Run the comparison to refresh the forecast.");
  }
  function reset() { scenarioBalance = ""; edits = {}; eventKey = ""; eventAmount = ""; invalidate(); }
  onMount(() => { void action(load); });
</script>

<div class="space-y-6">
  <header>
    <h1 class="text-2xl font-semibold">Family Finance Hub</h1>
    <p class="mt-2 text-muted-foreground">Plan checking cash flow with Runway’s scheduled payments, budgets and credit card statements.</p>
  </header>
  {#if basePath()}<p class="rounded border p-3">Opened securely through Home Assistant. Manual accounts only; bank synchronization is disabled.</p>{/if}
  <div class="flex flex-wrap gap-3"><Button class="min-h-11" href="#spending" variant="outline">Budget &amp; Spending</Button><Button class="min-h-11" href="#cardplanner" variant="outline">Smart Card Planner</Button></div>
  {#if error}<p role="alert" class="rounded-md border border-destructive p-3">{error}</p>{/if}
  {#if status}<p role="status">{status}</p>{/if}
  {#if busy}<p role="status">Working…</p>{/if}
  {#if error && !ready}<Button class="min-h-11" onclick={() => action(load)} disabled={busy}>Retry loading accounts</Button>{/if}
  {#if ready}
  <fieldset disabled={busy} class="space-y-6">
  <Card.Root>
    <Card.Header><Card.Title>Manual account balances</Card.Title><Card.Description>Save actual balances here. Bank-connected balances remain controlled by bank sync. Use negative balances for credit card debt.</Card.Description></Card.Header>
    <Card.Content class="space-y-4">
      {#each accounts.filter(a => a.provider === "manual" && !a.hidden) as a (a.id)}
        <form class="grid items-end gap-3 md:grid-cols-[1fr_1fr_auto]" onsubmit={(e) => { e.preventDefault(); void saved(() => apiCall<"POST /api/family/accounts">("/api/family/accounts", { method: "POST", body: { id: a.id, balance: balances[a.id], balance_date: balanceDates[a.id] } })); }}>
          <label class="space-y-1">{a.display_name || a.name} balance<Input class="min-h-11" aria-label={`${a.name} balance`} type="number" step="0.01" required bind:value={balances[a.id]} /></label>
          <label class="space-y-1">Balance date<Input class="min-h-11" aria-label={`${a.name} balance date`} type="date" required bind:value={balanceDates[a.id]} /></label>
          <Button class="min-h-11" type="submit" disabled={busy}>Save balance</Button>
        </form>
      {/each}
      <form class="grid items-end gap-3 md:grid-cols-4" onsubmit={(e) => { e.preventDefault(); void saved(async () => { await apiCall<"POST /api/family/accounts">("/api/family/accounts", { method: "POST", body: { name: accountName, kind: accountKind, balance: newBalance, balance_date: isoDay() } }); accountName = ""; newBalance = ""; }); }}>
        <label class="space-y-1">Account name<Input class="min-h-11" required bind:value={accountName} /></label>
        <label class="space-y-1">Account type<select aria-label="Account type" class={selectClass} bind:value={accountKind}>{#each ACCOUNT_KINDS.filter(k => k !== "investment" && k !== "loan") as kind (kind)}<option value={kind}>{KIND_LABEL[kind]}</option>{/each}</select></label>
        <label class="space-y-1">Opening balance<Input class="min-h-11" type="number" step="0.01" required bind:value={newBalance} /></label>
        <Button class="min-h-11" type="submit" disabled={busy}>Add manual account</Button>
      </form>
    </Card.Content>
  </Card.Root>

  <Card.Root>
    <Card.Header><Card.Title>Scheduled payments and income</Card.Title><Card.Description>Positive amounts are income; negative amounts are payments. Runway moves income to the prior business day and payments to the next business day.</Card.Description></Card.Header>
    <Card.Content class="space-y-4">
      <Button class="min-h-11" href="#recurring" variant="outline">Edit existing scheduled payments</Button>
      <form class="grid items-end gap-3 md:grid-cols-3" onsubmit={(e) => { e.preventDefault(); void saved(async () => { await api("/api/recurring", { method: "POST", body: { name: paymentName, account_id: paymentAccount, amount: paymentAmount, anchor_date: paymentDate, frequency, amount_mode: "fixed", active: 1 } }); paymentName = ""; paymentAmount = ""; }); }}>
        <label class="space-y-1">Payment or income name<Input class="min-h-11" required bind:value={paymentName} /></label>
        <label class="space-y-1">Amount<Input class="min-h-11" type="number" step="0.01" required bind:value={paymentAmount} /></label>
        <label class="space-y-1">Payment account<select class={selectClass} required bind:value={paymentAccount}><option value="" disabled>Choose an account</option>{#each accounts.filter(a => !a.hidden) as a (a.id)}<option value={a.id}>{a.display_name || a.name}</option>{/each}</select></label>
        <label class="space-y-1">Scheduled date<Input class="min-h-11" type="date" required bind:value={paymentDate} /></label>
        <label class="space-y-1">Frequency<select aria-label="Frequency" class={selectClass} bind:value={frequency}><option value="once">Once</option><option value="monthly">Monthly</option><option value="weekly">Weekly</option><option value="biweekly">Every two weeks</option></select></label>
        <Button class="min-h-11" type="submit" disabled={busy}>Add scheduled payment</Button>
      </form>
    </Card.Content>
  </Card.Root>

  <Card.Root>
    <Card.Header><Card.Title>Credit card payment modes</Card.Title><Card.Description>These settings affect the saved baseline. Custom amounts are capped at the remaining statement; unpaid amounts carry forward with interest when APR is set. Enter statements and APR in Settings → Accounts.</Card.Description></Card.Header>
    <Card.Content class="space-y-4">
      <Button class="min-h-11" href="#setup/accounts" variant="outline">Edit statements and account settings</Button>
      {#each cards as card (card.id)}
        <form class="grid items-end gap-3 md:grid-cols-4" onsubmit={(e) => { e.preventDefault(); void saved(() => api(`/api/accounts/${encodeURIComponent(card.id)}`, { method: "POST", body: { pay_mode: modes[card.id], pay_amount: modes[card.id] === "fixed" ? custom[card.id] : null, pay_from: payers[card.id] } })); }}>
          <label class="space-y-1">{card.display_name || card.name}<select aria-label={`${card.name} payment mode`} class={selectClass} bind:value={modes[card.id]}><option value="minimum">Minimum</option><option value="full">Full statement</option><option value="fixed">Custom amount</option></select></label>
          <label class="space-y-1">Pay from<select aria-label="Pay from" class={selectClass} required bind:value={payers[card.id]}><option value="" disabled>Choose an account</option>{#each cash as a (a.id)}<option value={a.id}>{a.display_name || a.name}</option>{/each}</select></label>
          {#if modes[card.id] === "fixed"}<label class="space-y-1">Custom payment<Input class="min-h-11" aria-label={`${card.name} custom payment`} type="number" min="0" step="0.01" required bind:value={custom[card.id]} /></label>{:else}<p class="text-sm text-muted-foreground">{modes[card.id] === "minimum" ? "Uses the issuer minimum, or Runway’s estimated minimum." : "Pays the remaining statement balance."}</p>{/if}
          <Button class="min-h-11" type="submit" disabled={busy}>Save payment mode</Button>
        </form>
      {/each}
      {#if !cards.length}<p>No credit cards yet. Add a manual credit card above.</p>{/if}
    </Card.Content>
  </Card.Root>

  <Card.Root>
    <Card.Header><Card.Title>November and December 2026</Card.Title><Card.Description>Balances are assumed to be opening balances on the forecast start date, plus Runway’s pending adjustments. This is a projection, not a reconstruction of historical cash flow. Select a checking account included in Overview’s forecast.</Card.Description></Card.Header>
    <Card.Content class="space-y-4">
      <div class="grid gap-3 md:grid-cols-3">
        <label class="space-y-1">Checking account<select aria-label="Checking account" class={selectClass} bind:value={accountId} disabled={busy} onchange={reset}><option value="" disabled>Choose checking</option>{#each checking as a (a.id)}<option value={a.id}>{a.display_name || a.name}</option>{/each}</select></label>
        <label class="space-y-1">Forecast start date<Input class="min-h-11" type="date" min="2026-01-01" max="2026-11-01" bind:value={start} disabled={busy} onchange={reset} /></label>
        <label class="space-y-1">What-if opening balance (optional)<Input class="min-h-11" type="number" step="0.01" bind:value={scenarioBalance} disabled={busy} oninput={invalidate} /></label>
      </div>
      <p class="text-sm text-muted-foreground">What-if changes are temporary and never saved. Reset or reload to discard them.</p>
      <div class="flex flex-wrap gap-3"><Button class="min-h-11" onclick={compare} disabled={busy || !accountId}>Compare cash flow</Button><Button class="min-h-11" variant="outline" onclick={reset} disabled={busy}>Reset scenario</Button></div>
      {#if Object.keys(edits).length}<p>{Object.keys(edits).length} temporary payment change(s) selected.</p>{/if}
      {#if result}
        {#each [...new Set([...result.warnings, ...result.scenario_warnings])] as warning (warning)}<p class="text-sm text-warning">{warning}</p>{/each}
        <form class="grid items-end gap-3 md:grid-cols-[2fr_1fr_auto]" onsubmit={(e) => { e.preventDefault(); if (eventKey && eventAmount !== "") { edits = { ...edits, [eventKey]: eventAmount }; eventKey = ""; eventAmount = ""; void compare(); } }}>
          <label class="space-y-1">What-if scheduled occurrence<select class={selectClass} required bind:value={eventKey}><option value="" disabled>Choose a payment or income</option>{#each result.events as event (event.key)}<option value={event.key}>{event.date} · {event.name} · {fmt(event.amount)}</option>{/each}</select></label>
          <label class="space-y-1">Scenario amount (signed)<Input class="min-h-11" type="number" step="0.01" required bind:value={eventAmount} /></label>
          <Button class="min-h-11" type="submit" disabled={busy}>Preview payment change</Button>
        </form>
        <div class="grid gap-4 lg:grid-cols-2">
          {#each result.baseline as month, index (month.month)}
            {@const scenario = result.scenario[index]}
            <section class="min-w-0 rounded-lg border p-4" aria-label={index === 0 ? "November 2026" : "December 2026"}>
              <h2 class="mb-3 text-xl font-semibold">{index === 0 ? "November" : "December"} 2026</h2>
              <div class="overflow-x-auto">
                <table class="w-full text-right text-sm tabular-nums">
                  <thead><tr><th class="p-2 text-left">Cash flow</th><th class="p-2">Baseline</th><th class="p-2">What-if</th></tr></thead>
                  <tbody>
                    {#each [["Opening", month.opening, scenario.opening], ["Income", month.income, scenario.income], ["Outflow incl. budgets", month.expenses, scenario.expenses], ["Net cash flow", month.net, scenario.net], ["Closing", month.closing, scenario.closing], ["Lowest daily balance", month.low.balance, scenario.low.balance]] as row (row[0])}
                      <tr><th class="p-2 text-left font-normal">{row[0]}</th><td class="p-2">{fmt(Number(row[1]))}</td><td class="p-2">{fmt(Number(row[2]))}</td></tr>
                    {/each}
                  </tbody>
                </table>
                <p class="my-3 text-sm">Lowest day: {month.low.date} · What-if: {scenario.low.date}</p>
                <details><summary class="min-h-11 cursor-pointer py-3 focus-visible:outline-2 focus-visible:outline-ring">Daily checking balances</summary>
                  <table class="w-full text-right text-sm tabular-nums"><thead><tr><th class="p-2 text-left">Date</th><th class="p-2">Baseline</th><th class="p-2">What-if</th></tr></thead><tbody>
                    {#each month.days as day, i (day.date)}<tr><th class="p-2 text-left font-normal">{day.date}</th><td class="p-2" class:text-destructive={day.balance < 0}>{fmt(day.balance)}</td><td class="p-2" class:text-destructive={scenario.days[i].balance < 0}>{fmt(scenario.days[i].balance)}</td></tr>{/each}
                  </tbody></table>
                </details>
              </div>
            </section>
          {/each}
        </div>
      {/if}
    </Card.Content>
  </Card.Root>
  </fieldset>
  {/if}
</div>
