// @vitest-environment jsdom
import { afterEach, expect, it } from "vitest";
import { appPath } from "./path";
afterEach(()=>document.head.querySelector('meta[name="runway-base-path"]')?.remove());
it("preserves ordinary URLs outside Ingress",()=>{expect(appPath("/api/accounts")).toBe("/api/accounts");});
it("keeps API and resource paths inside the Supervisor session without rewriting external URLs or hashes",()=>{
 const meta=document.createElement("meta");meta.name="runway-base-path";meta.content="/api/hassio_ingress/session";document.head.append(meta);
 expect(appPath("/api/accounts")).toBe(meta.content+"/api/accounts");
 expect(appPath(meta.content+"/logo.svg")).toBe(meta.content+"/logo.svg");
 expect(appPath("https://example.com")).toBe("https://example.com");expect(appPath("//example.com")).toBe("//example.com");expect(appPath("#family")).toBe("#family");
});
