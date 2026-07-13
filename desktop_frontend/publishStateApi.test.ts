import { beforeEach, describe, expect, it, vi } from "vitest";
import { publishStateApi } from "@/lib/api";

describe("desktop publish state API", () => {
  let requests: Array<{ url: string; init?: RequestInit }>;

  beforeEach(() => {
    requests = [];
    vi.restoreAllMocks();
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
        requests.push({ url: String(input), init });
        return new Response(
          JSON.stringify({
            event_id: 7,
            published_schedule_fingerprint: "event-fingerprint",
            published_schedule_scope: "partial",
            published_at: "2026-08-01T16:00:00Z",
            publish_failed_at: null,
            day_records: {
              "2026-08-01": {
                fingerprint: "day-1",
                publishedAt: "2026-08-01T16:00:00Z",
              },
            },
            last_publish_target: "both",
            last_publish_result_summary: "Arrival Day published successfully.",
          }),
          {
            status: 200,
            headers: { "Content-Type": "application/json" },
          },
        );
      }),
    );
  });

  it("fetches publish state from the backend instead of localStorage", async () => {
    const getItem = vi.spyOn(window.localStorage.__proto__, "getItem");

    const state = await publishStateApi.get(7);

    expect(requests[0].url).toContain("/api/v1/publish-state/7");
    expect(requests[0].init?.method).toBeUndefined();
    expect(getItem).not.toHaveBeenCalled();
    expect(state.day_records["2026-08-01"].fingerprint).toBe("day-1");
  });

  it("saves successful publish metadata with day records", async () => {
    await publishStateApi.save(7, {
      published_schedule_fingerprint: "event-fingerprint",
      published_schedule_scope: "all",
      published_at: "2026-08-01T16:00:00Z",
      day_records: {
        "2026-08-01": {
          fingerprint: "day-1",
          publishedAt: "2026-08-01T16:00:00Z",
          failedAt: null,
          failureMessage: null,
        },
      },
      last_publish_target: "both",
    });

    expect(requests[0].url).toContain("/api/v1/publish-state/7");
    expect(requests[0].init?.method).toBe("PUT");
    const requestBody = JSON.parse(String(requests[0].init?.body));
    expect(requestBody).toMatchObject({
      published_schedule_scope: "all",
      day_records: {
        "2026-08-01": {
          fingerprint: "day-1",
          publishedAt: "2026-08-01T16:00:00Z",
        },
      },
      last_publish_target: "both",
    });
    expect(requestBody.day_records["2026-08-01"].failedAt).toBeNull();
    expect(requestBody.day_records["2026-08-01"].failureMessage).toBeNull();
  });

  it("records failed publish metadata for affected days", async () => {
    await publishStateApi.recordFailure(7, {
      day_ids: ["2026-08-02"],
      failed_at: "2026-08-01T16:20:00Z",
      failure_message: "MP-Backend failed.",
      last_publish_target: "mp-backend",
    });

    expect(requests[0].url).toContain("/api/v1/publish-state/7/failure");
    expect(requests[0].init?.method).toBe("POST");
    expect(JSON.parse(String(requests[0].init?.body))).toEqual({
      day_ids: ["2026-08-02"],
      failed_at: "2026-08-01T16:20:00Z",
      failure_message: "MP-Backend failed.",
      last_publish_target: "mp-backend",
    });
  });

  it("clears publish metadata through the backend", async () => {
    await publishStateApi.clear(7);

    expect(requests[0].url).toContain("/api/v1/publish-state/7");
    expect(requests[0].init?.method).toBe("DELETE");
  });
});
