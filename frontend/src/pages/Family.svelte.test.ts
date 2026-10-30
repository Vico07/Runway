// @vitest-environment jsdom
import { cleanup, render, screen, waitFor, within } from "@testing-library/svelte";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, expect, it, vi } from "vitest";

vi.mock("$lib/api", async (orig) => ({ ...(await orig()), api: vi.fn() }));
import { api } from "$lib/api";
import Family from "./Family.svelte";

const account = { id: "manual:example", name: "Example checking", kind: "checking", balance: 1000,
  balance_date: "2026-10-29", provider: "manual", hidden: 0 };
const month = (key: string) => ({ month: key, opening: 1000, closing: 900, income: 0, expenses: 100, net: -100,
  low: { date: `${key}-10`, balance: 900 }, days: [{ date: `${key}-01`, balance: 1000 }, { date: `${key}-10`, balance: 900 }] });
const forecast = { start: "2026-11-01", account_id: account.id, baseline: [month("2026-11"), month("2026-12")],
  scenario: [month("2026-11"), month("2026-12")], warnings: [], scenario_warnings: [],
  events: [{ key: "rec:1:2026-11-10", name: "Example bill", date: "2026-11-10", amount: -100, kind: "recurring" }] };

beforeEach(() => {
  vi.mocked(api).mockReset();
  vi.mocked(api).mockImplementation((async (path: string) => {
    if (path === "/api/accounts") return [account];
    if (path === "/api/family/forecast") return structuredClone(forecast);
    return { ok: true };
  }) as never);
});
afterEach(cleanup);
const open = async () => { render(Family); await screen.findByRole("button", { name: "Compare cash flow" }); };
const compare = async () => {
  await userEvent.click(screen.getByRole("button", { name: "Compare cash flow" }));
  await screen.findByRole("region", { name: "November 2026" });
};

it("compares November and December with expandable daily checking balances", async () => {
  await open(); await compare();
  for (const name of ["November 2026", "December 2026"]) {
    const region = screen.getByRole("region", { name });
    expect(within(region).getByText("Lowest daily balance")).toBeInTheDocument();
    expect(within(region).getByText("Daily checking balances")).toBeInTheDocument();
  }
  expect(api).toHaveBeenCalledWith("/api/family/forecast", expect.objectContaining({ body: {
    start: "2026-11-01", account_id: account.id, balances: {}, edits: {},
  } }));
});

it("previews temporary payment changes and reset clears them without saving", async () => {
  await open(); await compare();
  await userEvent.selectOptions(screen.getByLabelText("What-if scheduled occurrence"), "rec:1:2026-11-10");
  await userEvent.type(screen.getByLabelText("Scenario amount (signed)"), "-250");
  await userEvent.click(screen.getByRole("button", { name: "Preview payment change" }));
  await waitFor(() => expect(api).toHaveBeenLastCalledWith("/api/family/forecast", expect.objectContaining({ body: expect.objectContaining({ edits: { "rec:1:2026-11-10": -250 } }) })));
  expect(vi.mocked(api).mock.calls.every(([path]) => path === "/api/accounts" || path === "/api/family/forecast")).toBe(true);
  await userEvent.click(screen.getByRole("button", { name: "Reset scenario" }));
  expect(screen.queryByRole("region", { name: "November 2026" })).not.toBeInTheDocument();
  await compare();
  expect(api).toHaveBeenLastCalledWith("/api/family/forecast", expect.objectContaining({ body: expect.objectContaining({ edits: {} }) }));
});

it("saves manual balances through the manual-only endpoint", async () => {
  await open();
  const balance = screen.getByRole("spinbutton", { name: "Example checking balance" });
  await userEvent.clear(balance); await userEvent.type(balance, "1250");
  await userEvent.click(screen.getByRole("button", { name: "Save balance" }));
  await waitFor(() => expect(api).toHaveBeenCalledWith("/api/family/accounts", expect.objectContaining({ body: {
    id: account.id, balance: 1250, balance_date: "2026-10-29",
  } })));
});

it("clears old results and reports a failed comparison", async () => {
  await open(); await compare();
  vi.mocked(api).mockRejectedValueOnce(new Error("Forecast unavailable"));
  await userEvent.click(screen.getByRole("button", { name: "Compare cash flow" }));
  expect(await screen.findByRole("alert")).toHaveTextContent("Forecast unavailable");
  expect(screen.queryByRole("region", { name: "November 2026" })).not.toBeInTheDocument();
});

it("reports load failure without presenting an empty account list as current", async () => {
  vi.mocked(api).mockRejectedValueOnce(new Error("Accounts unavailable"));
  render(Family);
  expect(await screen.findByRole("alert")).toHaveTextContent("Accounts unavailable");
  expect(screen.queryByRole("button", { name: "Add manual account" })).not.toBeInTheDocument();
});

it("creates a scheduled payment with the existing recurring endpoint", async () => {
  await open();
  await userEvent.type(screen.getByLabelText("Payment or income name"), "Example payment");
  await userEvent.type(screen.getByLabelText("Amount", { exact: true }), "-80");
  await userEvent.click(screen.getByRole("button", { name: "Add scheduled payment" }));
  await waitFor(() => expect(api).toHaveBeenCalledWith("/api/recurring", expect.objectContaining({ body: expect.objectContaining({
    name: "Example payment", account_id: account.id, amount: -80, frequency: "monthly", active: 1,
  }) })));
});

it("saves a card's custom payment mode through the existing account endpoint", async () => {
  vi.mocked(api).mockResolvedValueOnce([account, { id: "card", name: "Example card", kind: "credit", balance: -500,
    hidden: 0, pay_mode: "full", pay_from: account.id, provider: "manual" }]);
  await open();
  await userEvent.selectOptions(screen.getByLabelText("Example card payment mode"), "fixed");
  await userEvent.type(screen.getByLabelText("Example card custom payment"), "75");
  await userEvent.click(screen.getByRole("button", { name: "Save payment mode" }));
  await waitFor(() => expect(api).toHaveBeenCalledWith("/api/accounts/card", expect.objectContaining({ body: {
    pay_mode: "fixed", pay_amount: 75, pay_from: account.id,
  } })));
});
