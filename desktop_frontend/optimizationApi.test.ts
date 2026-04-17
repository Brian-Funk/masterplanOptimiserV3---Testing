/**
 * Tests for optimizationApi — start, poll, and list optimization jobs.
 */
import { describe, it, expect, vi, beforeEach } from "vitest";

// Mock environment
vi.mock("@/lib/environment", () => ({
  getApiUrl: () => "http://127.0.0.1:8000",
  isDesktopApp: () => true,
}));

const mockFetch = vi.fn();
vi.stubGlobal("fetch", mockFetch);

import { optimizationApi } from "@/lib/optimizationApi";

beforeEach(() => {
  mockFetch.mockReset();
});

describe("optimizationApi.startOptimization", () => {
  it("sends POST with JSON body", async () => {
    mockFetch.mockResolvedValue({
      ok: true,
      json: async () => ({ job_id: 42 }),
    });

    const request = {
      event_id: 1,
      date: "2026-08-01",
      tasks: [],
      persons: [],
      locations: [],
      capabilities: [],
    } as any;
    const result = await optimizationApi.startOptimization(request);

    expect(result).toEqual({ job_id: 42 });
    expect(mockFetch).toHaveBeenCalledWith(
      "http://127.0.0.1:8000/api/v1/optimize/day",
      expect.objectContaining({
        method: "POST",
        headers: { "Content-Type": "application/json" },
      }),
    );
  });

  it("throws on HTTP error", async () => {
    mockFetch.mockResolvedValue({
      ok: false,
      status: 500,
      json: async () => ({ detail: "Internal error" }),
    });

    await expect(
      optimizationApi.startOptimization({ event_id: 1 } as any),
    ).rejects.toThrow("Internal error");
  });

  it("handles 422 validation errors with detail array", async () => {
    mockFetch.mockResolvedValue({
      ok: false,
      status: 422,
      json: async () => ({
        detail: [
          { loc: ["body", "date"], msg: "field required" },
          { loc: ["body", "event_id"], msg: "must be positive" },
        ],
      }),
    });

    await expect(optimizationApi.startOptimization({} as any)).rejects.toThrow(
      "Validation errors",
    );
  });

  it("handles error when JSON parsing fails", async () => {
    mockFetch.mockResolvedValue({
      ok: false,
      status: 500,
      json: async () => {
        throw new Error("not json");
      },
    });

    await expect(
      optimizationApi.startOptimization({ event_id: 1 } as any),
    ).rejects.toThrow("Unknown error");
  });
});

describe("optimizationApi.getJobStatus", () => {
  it("fetches job status with correct URL", async () => {
    const job = { id: 42, status: "running", progress_data: {} };
    mockFetch.mockResolvedValue({
      ok: true,
      json: async () => job,
    });

    const result = await optimizationApi.getJobStatus(42, 1);

    expect(result).toEqual(job);
    expect(mockFetch).toHaveBeenCalledWith(
      "http://127.0.0.1:8000/api/v1/optimize/jobs/42?event_id=1",
    );
  });

  it("throws on HTTP error", async () => {
    mockFetch.mockResolvedValue({ ok: false, status: 404 });

    await expect(optimizationApi.getJobStatus(99, 1)).rejects.toThrow(
      "HTTP 404",
    );
  });
});

describe("optimizationApi.getJobsForEvent", () => {
  it("fetches jobs list for event", async () => {
    const jobs = { jobs: [{ id: 1 }, { id: 2 }] };
    mockFetch.mockResolvedValue({
      ok: true,
      json: async () => jobs,
    });

    const result = await optimizationApi.getJobsForEvent(5);

    expect(result).toEqual(jobs);
    expect(mockFetch).toHaveBeenCalledWith(
      "http://127.0.0.1:8000/api/v1/optimize/jobs?event_id=5",
    );
  });

  it("throws on HTTP error", async () => {
    mockFetch.mockResolvedValue({ ok: false, status: 403 });

    await expect(optimizationApi.getJobsForEvent(5)).rejects.toThrow(
      "HTTP 403",
    );
  });
});
