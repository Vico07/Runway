// @vitest-environment jsdom
import { render, screen, waitFor } from "@testing-library/svelte";
import userEvent from "@testing-library/user-event";
import { beforeEach, expect, it, vi } from "vitest";
vi.mock("$lib/api",async orig=>({...await orig(),api:vi.fn()}));
import { api } from "$lib/api";
import Planner from "./CardPlanner.svelte";
const initial={cards:[{id:"cc",name:"Example card",balance:-100}],profiles:{},checking:[{id:"chk",name:"Example checking"}],purchases:[],rules:[]};
const comparison={recommendation:null,options:[{card_id:"cc",name:"Example card",eligible:false,reasons:["Verify the grace period"],warnings:[],rewards:{units:0,unit:"unverified",dollars:null},net_cost:null,interest_estimate:null,fees:0,utilization:null,close:null,due:null,cashflow:null}],explanation:"Uncertain options are not ranked",notice:"Estimate only",debit:{net_cost:100,low:{balance:1000},reserve_protected:true},budget:{actual:0,planned:100,remaining_after:null}};
beforeEach(()=>{vi.mocked(api).mockReset();vi.mocked(api).mockImplementation((async(path:string)=>({data:path==="/api/cardplanner/quote"?comparison:initial})) as never);});
it("does not invent rewards or a recommendation when card terms are unknown",async()=>{
 render(Planner);await screen.findByRole("option",{name:/Example checking/});
 await userEvent.type(screen.getByLabelText("Merchant",{exact:true}),"Example shop");await userEvent.type(screen.getByLabelText("Purchase amount"),"100");
 await userEvent.click(screen.getByRole("button",{name:"Compare cards and debit"}));expect(await screen.findByText("No verified recommendation yet")).toBeInTheDocument();
 expect(screen.getByText("Verify the grace period")).toBeInTheDocument();expect(screen.getByRole("button",{name:/Save planned purchase on/})).toBeDisabled();
 expect(vi.mocked(api).mock.calls.every(([path])=>path==="/api/cardplanner"||path==="/api/cardplanner/quote")).toBe(true);
 await userEvent.click(screen.getByRole("button",{name:"Discard comparison"}));expect(screen.queryByRole("region",{name:"Card comparison"})).not.toBeInTheDocument();
});
it("saves only explicitly entered card profiles",async()=>{render(Planner);await screen.findByRole("option",{name:/Example card ·/});await userEvent.selectOptions(screen.getByLabelText("Card profile"),"cc");expect(screen.getByLabelText("Grace period")).toHaveValue("unknown");await userEvent.click(screen.getByRole("button",{name:"Save card profile"}));await waitFor(()=>expect(api).toHaveBeenCalledWith("/api/cardplanner/profile",expect.objectContaining({body:expect.objectContaining({data:expect.objectContaining({card_id:"cc",grace:"unknown",rewards:[]})})})))});
