/**
 * Tests for the packaged desktop Content Security Policy.
 */
import { describe, expect, it } from "vitest";
import { createRequire } from "node:module";
import path from "node:path";

const require = createRequire(import.meta.url);
const { buildDesktopContentSecurityPolicy } = require(
  path.resolve(
    process.cwd(),
    "..",
    "..",
    "MasterplanOptimiserV3 - App",
    "masterplanOptimiserV3 - App",
    "desktop",
    "security-policy.js",
  ),
);

describe("desktop packaged Content Security Policy", () => {
  it("allows Next.js inline bootstrap scripts without allowing eval", () => {
    const csp = buildDesktopContentSecurityPolicy();

    expect(csp).toContain("script-src 'self' 'unsafe-inline'");
    expect(csp).not.toContain("'unsafe-eval'");
  });

  it("allows the local backend and Google integration endpoints", () => {
    const csp = buildDesktopContentSecurityPolicy();

    expect(csp).toContain("http://127.0.0.1:8000");
    expect(csp).toContain("http://localhost:8000");
    expect(csp).toContain("https://www.googleapis.com");
    expect(csp).toContain("https://accounts.google.com");
    expect(csp).toContain("https://oauth2.googleapis.com");
  });

  it("limits local connections to the configured backend origins", () => {
    const csp = buildDesktopContentSecurityPolicy([
      "http://127.0.0.1:18123",
      "http://localhost:18123",
    ]);

    expect(csp).toContain("http://127.0.0.1:18123");
    expect(csp).toContain("http://localhost:18123");
    expect(csp).not.toContain("http://127.0.0.1:8000");
  });

  it("does not depend on remote Google font stylesheets", () => {
    const csp = buildDesktopContentSecurityPolicy();

    expect(csp).not.toContain("fonts.googleapis.com");
    expect(csp).not.toContain("fonts.gstatic.com");
  });

  it("keeps renderer hardening directives enabled", () => {
    const csp = buildDesktopContentSecurityPolicy();

    expect(csp).toContain("object-src 'none'");
    expect(csp).toContain("base-uri 'self'");
    expect(csp).toContain("form-action 'self'");
    expect(csp).toContain("frame-ancestors 'none'");
  });
});
