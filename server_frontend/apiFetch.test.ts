/**
 * Tests for the apiFetch wrapper — CSRF, credentials, content-type.
 */
import { describe, it, expect, vi, beforeEach } from "vitest";

// Mock environment
vi.mock("@/lib/environment", () => ({
  getApiUrl: () => "https://api.test",
}));

// Mock fetch
const mockFetch = vi.fn();
vi.stubGlobal("fetch", mockFetch);

// Simulate csrf_token cookie
Object.defineProperty(document, "cookie", {
  writable: true,
  value: "csrf_token=test-csrf-123",
});

import { apiFetch } from "@/lib/api";

beforeEach(() => {
  mockFetch.mockReset();
  mockFetch.mockResolvedValue(new Response("{}", { status: 200 }));
});

describe("apiFetch", () => {
  it("prepends API URL to path", async () => {
    await apiFetch("/api/v1/events");
    expect(mockFetch).toHaveBeenCalledWith(
      "https://api.test/api/v1/events",
      expect.any(Object),
    );
  });

  it("includes credentials", async () => {
    await apiFetch("/api/v1/events");
    expect(mockFetch).toHaveBeenCalledWith(
      expect.any(String),
      expect.objectContaining({ credentials: "include" }),
    );
  });

  it("adds CSRF header on POST", async () => {
    await apiFetch("/api/v1/events", { method: "POST", body: "{}" });
    const call = mockFetch.mock.calls[0];
    expect(call[1].headers["X-CSRF-Token"]).toBe("test-csrf-123");
  });

  it("adds CSRF header on DELETE", async () => {
    await apiFetch("/api/v1/events/1", { method: "DELETE" });
    const call = mockFetch.mock.calls[0];
    expect(call[1].headers["X-CSRF-Token"]).toBe("test-csrf-123");
  });

  it("does NOT add CSRF on GET", async () => {
    await apiFetch("/api/v1/events");
    const call = mockFetch.mock.calls[0];
    expect(call[1].headers["X-CSRF-Token"]).toBeUndefined();
  });

  it("sets Content-Type for string body", async () => {
    await apiFetch("/api/v1/events", {
      method: "POST",
      body: JSON.stringify({ name: "test" }),
    });
    const call = mockFetch.mock.calls[0];
    expect(call[1].headers["Content-Type"]).toBe("application/json");
  });

  it("uses no-store cache", async () => {
    await apiFetch("/api/v1/events");
    const call = mockFetch.mock.calls[0];
    expect(call[1].cache).toBe("no-store");
  });
});
