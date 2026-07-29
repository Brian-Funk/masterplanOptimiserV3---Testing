/**
 * Tests for environment detection utility.
 */
import { describe, it, expect, vi, beforeEach } from "vitest";

beforeEach(() => {
  vi.resetModules();
  // @ts-ignore
  delete window.electron;
});

describe("isDesktopApp", () => {
  it("returns false in normal browser (no Electron)", async () => {
    const { isDesktopApp } = await import("@/lib/environment");
    expect(isDesktopApp()).toBe(false);
  });

  it("returns true when window.electron.isElectron is set", async () => {
    // @ts-ignore
    window.electron = { isElectron: true };
    const { isDesktopApp } = await import("@/lib/environment");
    expect(isDesktopApp()).toBe(true);
    // @ts-ignore
    delete window.electron;
  });
});

describe("getApiUrl", () => {
  it("returns localhost URL in non-Electron env", async () => {
    const { getApiUrl } = await import("@/lib/environment");
    const url = getApiUrl();
    expect(url).toContain("127.0.0.1:8000");
  });

  it("uses the loopback URL supplied by the Electron shell", async () => {
    // @ts-ignore
    window.electron = {
      isElectron: true,
      apiUrl: "http://127.0.0.1:18123",
    };
    const { getApiUrl } = await import("@/lib/environment");

    expect(getApiUrl()).toBe("http://127.0.0.1:18123");
  });

  it("fails closed when Electron omits its API URL", async () => {
    // @ts-ignore
    window.electron = { isElectron: true };
    const { getApiUrl } = await import("@/lib/environment");

    expect(() => getApiUrl()).toThrow(/API URL was not provided/);
  });
});
