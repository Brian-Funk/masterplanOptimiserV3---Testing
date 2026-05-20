/**
 * Tests for the desktop startup integrity checklist helper.
 */
import { describe, expect, it } from "vitest";
import { createRequire } from "node:module";
import path from "node:path";

const require = createRequire(import.meta.url);
const startupScreen = require(
  path.resolve(
    process.cwd(),
    "..",
    "..",
    "MasterplanOptimiserV3 - App",
    "masterplanOptimiserV3 - App",
    "desktop",
    "startup-screen.js",
  ),
);

const {
  buildStartupSteps,
  describeIntegrityResult,
  renderStartupPageHtml,
} = startupScreen;

describe("desktop startup screen helper", () => {
  it("renders the compact startup checklist", () => {
    const html = renderStartupPageHtml({
      status: "Checking application integrity...",
      steps: buildStartupSteps({
        integrity: {
          state: "checking",
          detail: "Checking application integrity",
        },
      }),
    });

    expect(html).toContain("Masterplan Optimiser");
    expect(html).toContain("Checking application integrity...");
    expect(html).toContain("Integrity");
    expect(html).toContain("Backend");
    expect(html).toContain("Interface");
    expect(html).toContain("step-checking");
  });

  it("shows all supported startup states", () => {
    const html = renderStartupPageHtml({
      status: "Starting",
      steps: [
        { id: "one", label: "Pending", state: "pending", detail: "Waiting" },
        { id: "two", label: "Checking", state: "checking", detail: "Working" },
        { id: "three", label: "Complete", state: "complete", detail: "Done" },
        { id: "four", label: "Warning", state: "warning", detail: "Review" },
        { id: "five", label: "Failed", state: "failed", detail: "Stopped" },
        { id: "six", label: "Skipped", state: "skipped", detail: "Skipped" },
      ],
    });

    expect(html).toContain("step-pending");
    expect(html).toContain("step-checking");
    expect(html).toContain("step-complete");
    expect(html).toContain("step-warning");
    expect(html).toContain("step-failed");
    expect(html).toContain("step-skipped");
  });

  it("escapes status and step details before rendering", () => {
    const html = renderStartupPageHtml({
      status: '<img src=x onerror="alert(1)">',
      steps: [
        {
          id: "integrity",
          label: "Integrity",
          state: "failed",
          detail: 'A & B "modified" <file>',
        },
      ],
    });

    expect(html).toContain("&lt;img src=x onerror=&quot;alert(1)&quot;&gt;");
    expect(html).not.toContain('<img src=x onerror="alert(1)">');
    expect(html).toContain("A &amp; B &quot;modified&quot; &lt;file&gt;");
  });

  it("maps a running integrity check to the checking state", () => {
    expect(describeIntegrityResult(null)).toEqual({
      state: "checking",
      status: "Checking application integrity...",
      detail: "Checking application integrity...",
    });
  });

  it("maps development mode integrity to a skipped state", () => {
    expect(describeIntegrityResult({ dev: true, valid: true })).toEqual({
      state: "skipped",
      status: "Development mode - integrity check skipped",
      detail: "Development mode - integrity check skipped",
    });
  });

  it("maps successful signed integrity to a complete state", () => {
    expect(describeIntegrityResult({ valid: true, signatureOk: true })).toEqual({
      state: "complete",
      status: "Integrity verified",
      detail: "Verified signed resources",
    });
  });

  it("maps failed integrity to a failed state with a useful detail", () => {
    expect(
      describeIntegrityResult({
        valid: false,
        error: "Modified files detected",
      }),
    ).toEqual({
      state: "failed",
      status: "Integrity check failed",
      detail: "Modified files detected",
    });
  });
});
