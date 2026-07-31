import fs from "node:fs";
import path from "node:path";
import { describe, expect, it } from "vitest";


const appRoot = process.env.MP_OPT_APP_ROOT || path.resolve(
  process.cwd(),
  "..",
  "..",
  "MasterplanOptimiserV3 - App",
  "masterplanOptimiserV3 - App",
);


function source(relative: string) {
  return fs.readFileSync(path.join(appRoot, relative), "utf8");
}


describe("desktop operator evidence custody", () => {
  it("exposes generation and both bounded signing flows in Settings", () => {
    const settings = source(
      "web/src/app/dashboard/settings/components/OperatorEvidenceSection.tsx",
    );
    const api = source("web/src/lib/api.ts");

    expect(settings).toContain("Accountability signing keys");
    expect(settings).toContain('sign("registration")');
    expect(settings).toContain('sign("anchor")');
    expect(settings).toContain("Private keys stay in the operating-system credential store");
    expect(api).toContain("/api/v1/operator-evidence/keys");
    expect(api).toContain("/sign-registration");
    expect(api).toContain("/sign-anchor");
  });

  it("keeps SQLite metadata public-only and the private key in the keyring boundary", () => {
    const model = source("backend/app/models/operator_evidence.py");
    const custody = source("backend/app/core/operator_evidence.py");

    expect(model).toContain("public_key = Column");
    expect(model).toContain("public_key_sha256 = Column");
    expect(model).not.toMatch(/private_key\s*=\s*Column/);
    expect(custody).toContain("set_secret(account, _private_pem(private))");
    expect(custody).toContain("Private-key material is not accepted");
    expect(custody).toContain("This role is not authorised to sign Git anchors");
  });

  it("documents that local retirement follows Server revocation and retains history", () => {
    const settings = source(
      "web/src/app/dashboard/settings/components/OperatorEvidenceSection.tsx",
    );
    expect(settings).toContain("Retire after Server revocation");
    expect(settings).toContain("Historic key material was not silently erased");
  });
});
