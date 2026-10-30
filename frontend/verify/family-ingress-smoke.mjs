// Opt-in test against tools/family_deployment_smoke.py's synthetic gateway only. Never targets a household instance.
import { chromium, expect as rawExpect } from "@playwright/test";
import { writeFileSync } from "node:fs";
const expect = rawExpect.configure({timeout:15000});
const base = process.argv[2];
if (base !== "http://127.0.0.1:18888") throw new Error("Only the isolated local synthetic gateway is supported");
const prefix = "/api/hassio_ingress/synthetic_session";
const browser = await chromium.launch({ executablePath: process.env.RUNWAY_TEST_CHROMIUM || "/usr/bin/chromium" });
const today = new Intl.DateTimeFormat("en-CA", { timeZone: "America/New_York" }).format(new Date());
const current = new Date(today + "T12:00:00Z");
const closing = new Date(Date.UTC(current.getUTCFullYear(), current.getUTCMonth() - (current.getUTCDate() > 15 ? 0 : 1), 15));
const due = new Date(Date.UTC(closing.getUTCFullYear(), closing.getUTCMonth() + 1, 5));
const tomorrow = new Date(current); tomorrow.setUTCDate(current.getUTCDate() + 1);
try {
 for (const [name, viewport] of [["iphone", {width:440,height:956}], ["desktop", {width:1280,height:800}]]) {
  const context = await browser.newContext({viewport, isMobile:name==="iphone",hasTouch:name==="iphone",timezoneId:"America/New_York"});
  const page = await context.newPage();
  const response = await page.goto(base);
  if (response.headers()["x-runway-test-gateway"] !== "1") throw new Error("Refusing to edit a non-fixture service");
  const frame = page.frameLocator("#ingress");
  expect(await frame.locator("body").evaluate(e=>e.ownerDocument.defaultView.innerWidth)).toBe(viewport.width);
  const errors=[];
  page.on("console",m=>{if(m.type()==="error") console.error(m.text());});
  page.on("pageerror",e=>errors.push(e.message));
  await expect(frame.getByRole("heading",{name:"Family Finance Hub",exact:true})).toBeVisible();
  await expect(frame.getByRole("button",{name:"Add manual account",exact:true})).toBeVisible();
  let accounts = await (await page.request.get(base+prefix+"/api/accounts")).json();
  if(process.argv.includes("--read-only")) {
   expect(accounts.some(a=>a.name==="Synthetic checking")).toBe(true);
   expect(accounts.some(a=>a.name==="Synthetic card")).toBe(true);
   await context.close(); continue;
  }
  if(!accounts.length) {
   await frame.getByLabel("Account name",{exact:true}).fill("Synthetic checking");
   await frame.getByLabel("Opening balance",{exact:true}).fill("2000");
   await frame.getByRole("button",{name:"Add manual account",exact:true}).click();
   await expect(frame.getByLabel("Synthetic checking balance",{exact:true})).toBeVisible({timeout:15000});
   await frame.getByLabel("Account name",{exact:true}).fill("Synthetic card");
   await frame.getByLabel("Account type",{exact:true}).selectOption("credit");
   await frame.getByLabel("Opening balance",{exact:true}).fill("0");
   await frame.getByRole("button",{name:"Add manual account",exact:true}).click();
   await expect(frame.getByLabel("Synthetic card payment mode")).toBeVisible();
   accounts = await (await page.request.get(base+prefix+"/api/accounts")).json();
   const checking=accounts.find(a=>a.name==="Synthetic checking");
   await frame.getByLabel("Pay from",{exact:true}).selectOption(checking.id);
   await frame.getByRole("button",{name:"Save payment mode",exact:true}).click();
   await expect(frame.getByRole("status").filter({hasText:"Saved"})).toBeVisible();
   await frame.getByRole("link",{name:"Smart Card Planner",exact:true}).last().click();
   await frame.getByLabel("Card profile",{exact:true}).selectOption(accounts.find(a=>a.name==="Synthetic card").id);
   for(const [label,value] of [["Credit limit","5000"],["Available credit","5000"],["Purchase APR (%)","20"],["Statement closing day","15"],["Payment due day","5"],["Actual statement balance","0"],["Issuer minimum payment","0"]]) await frame.getByLabel(label,{exact:true}).fill(value);
   for(const [label,value] of [["Actual last closing date",closing.toISOString().slice(0,10)],["Actual statement due date",due.toISOString().slice(0,10)],["Last verification date",today]]) await frame.getByLabel(label,{exact:true}).fill(value);
   await frame.getByLabel("Grace period",{exact:true}).selectOption("active");
   await frame.getByLabel("Issuer terms / data source",{exact:true}).fill("Synthetic deployment fixture, not issuer benefits");
   await frame.getByLabel("Rewards terms (JSON)",{exact:true}).fill('[{"unit":"USD","rate":2}]');
   await frame.getByLabel("I verified the rewards, including caps and usage",{exact:true}).check();
   await frame.getByRole("button",{name:"Save card profile",exact:true}).click();
   await expect(frame.getByRole("status").filter({hasText:"profile saved"})).toBeVisible();
  } else {
   await frame.getByRole("link",{name:"Smart Card Planner",exact:true}).last().click();
  }
  await frame.getByLabel("Merchant",{exact:true}).fill("Synthetic planned shop");
  await frame.getByLabel("Budget category",{exact:true}).fill("Groceries");
  await frame.getByLabel("Purchase amount",{exact:true}).fill("100");
  await frame.getByLabel("Proposed purchase date",{exact:true}).fill(tomorrow.toISOString().slice(0,10));
  await frame.getByRole("button",{name:"Compare cards and debit",exact:true}).click();
  await expect(frame.getByRole("region",{name:"Card comparison"})).toBeVisible();
  await expect(frame.getByRole("heading",{name:"Recommended: Synthetic card",exact:true})).toBeVisible();
  await frame.getByRole("button",{name:"Save planned purchase on Synthetic card",exact:true}).click();
  await expect(frame.getByRole("status").filter({hasText:"Planned purchase saved"})).toBeVisible();
  await frame.getByRole("link",{name:"Budget & Spending",exact:true}).last().click();
  await expect(frame.getByRole("heading",{name:"Budget & Spending",exact:true})).toBeVisible();
  await frame.getByRole("link",{name:"Import",exact:true}).click();
  await frame.getByLabel("Account",{exact:true}).selectOption(accounts.find(a=>a.name==="Synthetic card").id);
  await frame.getByLabel("CSV contents",{exact:true}).fill(`date,amount,description,merchant,category\n${today},-12.50,SYNTHETIC CSV RECORD,Synthetic market,Groceries`);
  await frame.getByRole("button",{name:"Import transactions",exact:true}).click();
  await expect(frame.getByRole("status").filter({hasText:"added"})).toBeVisible();
  await frame.getByRole("navigation",{name:"Budget & Spending",exact:true}).getByRole("link",{name:"Overview",exact:true}).click();
  await expect(frame.getByRole("heading",{name:"Freshness, coverage and reconciliation",exact:true})).toBeVisible();
  await frame.getByText("Imported transaction details (first 500)",{exact:true}).click();
  await expect(frame.getByText("SYNTHETIC CSV RECORD",{exact:true})).toBeVisible();
  expect(errors).toEqual([]);
  await frame.locator("body").evaluate(e=>e.ownerDocument.defaultView.scrollTo(0,0));
  await page.screenshot({path:`artifacts/ingress-${name}.png`,fullPage:true});
  await context.close();
 }
} catch(error) {
  const evidence=[];
  for(const context of browser.contexts()) for(const page of context.pages()) for(const frame of page.frames())
    evidence.push(await frame.locator("body").innerText().catch(()=>"Frame unavailable"));
  writeFileSync("artifacts/ingress-failure.txt",evidence.join("\n"));
  throw error;
} finally { await browser.close(); }
