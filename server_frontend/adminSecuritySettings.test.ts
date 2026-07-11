/**
 * Static checks for root-admin security settings wiring.
 */
import { describe, expect, it } from "vitest";
import { readFileSync } from "node:fs";
import path from "node:path";

const serverRoot = path.resolve(
  __dirname,
  "../../..",
  "MasterplanOptimiserV3 - Server",
  "MasterplanOptimiserV3---Server",
);
const adminPagePath = path.join(
  serverRoot,
  "web",
  "src",
  "app",
  "admin",
  "page.tsx",
);

function adminPageSource(): string {
  return readFileSync(adminPagePath, "utf8");
}

describe("admin security settings", () => {
  it("shows the offline calendar window in its own security section", () => {
    const source = adminPageSource();

    expect(source).toContain('title: "Offline Access"');
    expect(source).toContain('"offline_access_ttl_hours"');
    expect(source).toContain("cached masterplan while offline");
  });

  it("limits the Security tab to root admins", () => {
    const source = adminPageSource();

    expect(source).toContain('t.key === "security"');
    expect(source).toContain("user?.is_root_admin");
    expect(source).toContain('tab === "security" && user?.is_root_admin');
  });
});
