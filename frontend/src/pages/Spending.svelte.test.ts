// @vitest-environment jsdom
import { render, screen, waitFor } from "@testing-library/svelte";
import userEvent from "@testing-library/user-event";
import { beforeEach, expect, it, vi } from "vitest";
vi.mock("$lib/api",async orig=>({...await orig(),api:vi.fn()}));
import { api } from "$lib/api";
import Spending from "./Spending.svelte";
const snapshot={month:"2026-09",spent:85,fixed:0,variable:85,prior_comparable:70,remaining_estimate:20,unallocated_debt:0,
 estimate_method:"Estimate only",warnings:["No statement reconciliation confirmed"],uncategorized:1,last_dates:[],subscriptions:[],
 categories:[{name:"Groceries",spent:85,budget:100,remaining:15,warning:"near"}],merchants:[{name:"Example shop",spent:85}],weekly:[],monthly:[],transactions:[],accounts:[{id:"chk",name:"Example checking"}]};
beforeEach(()=>{vi.mocked(api).mockReset();vi.mocked(api).mockResolvedValue({data:snapshot});});
it("shows category budgets, drill-down and reconciliation uncertainty",async()=>{
 render(Spending);expect(await screen.findByText("Approaching budget")).toBeInTheDocument();expect(screen.getByText("No statement reconciliation confirmed")).toBeInTheDocument();
 await userEvent.click(screen.getByRole("button",{name:/^Groceries$/}));expect(location.hash).toContain("category=Groceries");
});
it("keeps stale numbers off screen when loading fails",async()=>{vi.mocked(api).mockRejectedValueOnce(new Error("Unavailable"));render(Spending);expect(await screen.findByRole("alert")).toHaveTextContent("Unavailable");expect(screen.queryByText("Approaching budget")).not.toBeInTheDocument();});
it("imports CSV through the existing validated importer adapter",async()=>{
 vi.mocked(api).mockImplementation((async(path:string)=>path==="/api/spending/import"?{data:{added:1,skipped:0,rows:[]}}:{data:snapshot}) as never);
 render(Spending,{props:{sub:"import"}});await screen.findByRole("option",{name:"Example checking"});
 await userEvent.type(screen.getByLabelText("CSV contents"),"date,amount,description\n2026-09-01,-10,SYNTHETIC");await userEvent.click(screen.getByRole("button",{name:"Import transactions"}));
 await waitFor(()=>expect(api).toHaveBeenCalledWith("/api/spending/import",expect.objectContaining({body:{data:{account:"chk",csv:"date,amount,description\n2026-09-01,-10,SYNTHETIC"}}})));
 expect(await screen.findByRole("status")).toHaveTextContent("1 added");
});
