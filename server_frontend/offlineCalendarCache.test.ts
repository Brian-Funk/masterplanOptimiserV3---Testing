/**
 * Tests for offline calendar payload storage.
 */
import { beforeEach, describe, expect, it, vi } from "vitest";
import {
  clearOfflineCalendarCacheForUser,
  getOfflineCalendarPayload,
  storeOfflineCalendarPayload,
} from "@/lib/offlineCalendarCache";

const payload = {
  event_id: 7,
  event_name: "Cached Event",
  tasks: [{ id: 1, name: "Opening" }],
};

function disableIndexedDb(): void {
  try {
    Object.defineProperty(window, "indexedDB", {
      configurable: true,
      value: undefined,
    });
  } catch {
    /* keep the environment default */
  }
}

beforeEach(() => {
  localStorage.clear();
  vi.restoreAllMocks();
  disableIndexedDb();
});

describe("offlineCalendarCache", () => {
  it("stores and reads a calendar payload for the same user and event", async () => {
    await storeOfflineCalendarPayload(
      12,
      7,
      payload,
      "2026-05-21T09:30:00.000Z",
    );

    const cached = await getOfflineCalendarPayload<typeof payload>(12, 7);

    expect(cached).toMatchObject({
      user_id: 12,
      event_id: 7,
      cached_at: "2026-05-21T09:30:00.000Z",
      payload,
    });
  });

  it("does not return another user or event's payload", async () => {
    await storeOfflineCalendarPayload(12, 7, payload);

    await expect(getOfflineCalendarPayload(13, 7)).resolves.toBeNull();
    await expect(getOfflineCalendarPayload(12, 8)).resolves.toBeNull();
  });

  it("clears cached payloads for one user", async () => {
    await storeOfflineCalendarPayload(12, 7, payload);
    await storeOfflineCalendarPayload(13, 7, { event_name: "Other" });

    await clearOfflineCalendarCacheForUser(12);

    await expect(getOfflineCalendarPayload(12, 7)).resolves.toBeNull();
    await expect(getOfflineCalendarPayload(13, 7)).resolves.toMatchObject({
      payload: { event_name: "Other" },
    });
  });

  it("does not throw when browser storage is unavailable", async () => {
    vi.spyOn(Storage.prototype, "setItem").mockImplementation(() => {
      throw new Error("storage unavailable");
    });
    vi.spyOn(Storage.prototype, "getItem").mockImplementation(() => {
      throw new Error("storage unavailable");
    });

    await expect(
      storeOfflineCalendarPayload(12, 7, payload),
    ).resolves.toMatchObject({
      user_id: 12,
      event_id: 7,
    });
    await expect(getOfflineCalendarPayload(12, 7)).resolves.toBeNull();
  });
});
