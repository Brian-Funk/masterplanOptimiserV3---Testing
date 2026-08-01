import fs from "node:fs";
import path from "node:path";
import { describe, expect, it } from "vitest";
import { resolveAppRoot } from "../test_support/repoRoots";

const appRoot = resolveAppRoot();


function source(relative: string) {
  return fs.readFileSync(path.join(appRoot, relative), "utf8");
}


describe("desktop processor evidence custody", () => {
  it("exposes generation and both bounded signing flows in Settings", () => {
    const settings = source(
      "web/src/app/dashboard/settings/components/ProcessorEvidenceSection.tsx",
    );
    const api = source("web/src/lib/api.ts");

    expect(settings).toContain("Processor signing key");
    expect(settings).toContain('sign("registration")');
    expect(settings).toContain('sign("statement")');
    expect(settings).toContain("private key stays in the operating-system credential store");
    expect(settings).toContain("Controller keys are created with the separate controller-custody utility");
    expect(api).toContain("/api/v1/processor-evidence/keys");
    expect(api).toContain("/sign-registration");
    expect(api).toContain("/sign-statement");
  });

  it("keeps SQLite metadata public-only and the private key in the keyring boundary", () => {
    const model = source("backend/app/models/operator_evidence.py");
    const custody = source("backend/app/core/operator_evidence.py");

    expect(model).toContain("public_key = Column");
    expect(model).toContain("public_key_sha256 = Column");
    expect(model).not.toMatch(/private_key\s*=\s*Column/);
    expect(model).toContain("class ProcessorEvidenceKey");
    expect(custody).toContain("set_secret(account, secret)");
    expect(custody).toContain("Private-key material is not accepted");
    expect(custody).toContain("no controller-key generation or signing API exists in Desktop");
  });

  it("documents that local retirement follows Server revocation and retains history", () => {
    const settings = source(
      "web/src/app/dashboard/settings/components/ProcessorEvidenceSection.tsx",
    );
    expect(settings).toContain("Retire after Server revocation");
    expect(settings).toContain("Historic verification material remains available");
  });
});
