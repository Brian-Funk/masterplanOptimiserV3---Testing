import fs from "node:fs";
import path from "node:path";
import { describe, expect, it } from "vitest";
import { resolveAppRoot } from "../test_support/repoRoots";

const appRoot = resolveAppRoot();


function source(relative: string) {
  return fs.readFileSync(path.join(appRoot, relative), "utf8");
}


describe("desktop processor evidence custody", () => {
  it("exposes event-scoped generation and import without raw signing controls", () => {
    const settings = source(
      "web/src/app/dashboard/settings/components/ProcessorEvidenceSection.tsx",
    );
    const api = source("web/src/lib/api.ts");

    expect(settings).toContain("One processor identity is bound to");
    expect(settings).toContain("Generate on this Desktop");
    expect(settings).toContain("Import an encrypted key");
    expect(settings).toContain("listKeys(selectedEventId)");
    expect(settings).toContain("enrolKey(selectedEventId");
    expect(settings).not.toContain('sign("registration")');
    expect(settings).not.toContain('sign("statement")');
    expect(api).toContain("/api/v1/processor-evidence/keys");
    expect(api).toContain("/enrol");
    expect(api).toContain("/refresh-status");
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

  it("scopes the active panel to the selected Server event without deleting history", () => {
    const settings = source(
      "web/src/app/dashboard/settings/components/ProcessorEvidenceSection.tsx",
    );
    const api = source("web/src/lib/api.ts");
    const backend = source("backend/app/api/v1/operator_evidence.py");
    const custody = source("backend/app/core/operator_evidence.py");

    expect(settings).toContain("The selected event is the scope boundary");
    expect(settings).toContain('"Setup required"');
    expect(settings).toContain("Event identity");
    expect(api).toContain("?event_id=${encodeURIComponent(eventId)}");
    expect(backend).toContain("ProcessorEvidenceKey.event_evidence_id == event.evidence_id");
    expect(backend).toContain("retire_key(db");
    expect(custody).toContain('row.state = "retired"');
  });
});
