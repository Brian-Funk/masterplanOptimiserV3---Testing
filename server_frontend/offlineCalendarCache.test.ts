/** Tests for IndexedDB-only offline calendar payload storage. */
import { beforeEach, describe, expect, it } from "vitest";
import {
  clearOfflineCalendarCacheForUser,
  getOfflineCalendarPayload,
  setOfflineCalendarStorageEnabled,
  storeOfflineCalendarPayload,
} from "@/lib/offlineCalendarCache";

const payload = {
  event_id: 7,
  event_name: "Cached Event",
  tasks: [],
  persons: [],
};

const cachedAt = "2026-05-21T09:30:00.000Z";
const validUntil = "2026-08-21T09:30:00.000Z";
const validationTime = new Date("2026-05-21T09:30:00.000Z");

const records = new Map<string, Record<string, unknown>>();

function installMemoryIndexedDb(): void {
  let storeCreated = false;
  const database = {
    objectStoreNames: {
      contains: () => storeCreated,
    },
    createObjectStore: () => {
      storeCreated = true;
      return {};
    },
    deleteObjectStore: () => {
      storeCreated = false;
      records.clear();
    },
    transaction: () => {
      const transaction: Record<string, unknown> = {};
      const store = {
        put: (record: Record<string, unknown>) => {
          records.set(String(record.id), record);
          queueMicrotask(() =>
            (transaction.oncomplete as (() => void) | undefined)?.(),
          );
          return {};
        },
        get: (key: string) => {
          const request: Record<string, unknown> = {};
          queueMicrotask(() => {
            request.result = records.get(key);
            (request.onsuccess as (() => void) | undefined)?.();
            queueMicrotask(() =>
              (transaction.oncomplete as (() => void) | undefined)?.(),
            );
          });
          return request;
        },
        getAll: () => {
          const request: Record<string, unknown> = {};
          queueMicrotask(() => {
            request.result = Array.from(records.values());
            (request.onsuccess as (() => void) | undefined)?.();
            queueMicrotask(() =>
              (transaction.oncomplete as (() => void) | undefined)?.(),
            );
          });
          return request;
        },
        delete: (key: string) => {
          records.delete(key);
          return {};
        },
      };
      transaction.objectStore = () => store;
      return transaction;
    },
    close: () => undefined,
  };
  const indexedDb = {
    open: () => {
      const request: Record<string, unknown> = {};
      queueMicrotask(() => {
        request.result = database;
        if (!storeCreated) {
          (request.onupgradeneeded as (() => void) | undefined)?.();
        }
        (request.onsuccess as (() => void) | undefined)?.();
      });
      return request;
    },
  };
  Object.defineProperty(window, "indexedDB", {
    configurable: true,
    value: indexedDb as unknown as IDBFactory,
  });
}

function disableIndexedDb(): void {
  Object.defineProperty(window, "indexedDB", {
    configurable: true,
    value: undefined,
  });
}

beforeEach(() => {
  records.clear();
  localStorage.clear();
  installMemoryIndexedDb();
  setOfflineCalendarStorageEnabled(12, true);
  setOfflineCalendarStorageEnabled(13, true);
});

describe("offlineCalendarCache", () => {
  it("stores and reads a payload for the same user and event", async () => {
    await storeOfflineCalendarPayload(
      12,
      7,
      payload,
      cachedAt,
      validUntil,
      validationTime,
    );

    await expect(getOfflineCalendarPayload<typeof payload>(12, 7, validationTime)).resolves.toMatchObject({
      user_id: 12,
      event_id: 7,
      cached_at: cachedAt,
      valid_until: validUntil,
      payload,
    });
    expect(localStorage.length).toBe(2);
  });

  it("does not return another user or event's payload", async () => {
    await storeOfflineCalendarPayload(12, 7, payload, cachedAt, validUntil, validationTime);

    await expect(getOfflineCalendarPayload(13, 7, validationTime)).resolves.toBeNull();
    await expect(getOfflineCalendarPayload(12, 8, validationTime)).resolves.toBeNull();
  });

  it("clears cached payloads for only the selected user", async () => {
    await storeOfflineCalendarPayload(12, 7, payload, cachedAt, validUntil, validationTime);
    await storeOfflineCalendarPayload(
      13,
      7,
      { ...payload, event_name: "Other" },
      cachedAt,
      validUntil,
      validationTime,
    );

    await clearOfflineCalendarCacheForUser(12);

    await expect(getOfflineCalendarPayload(12, 7, validationTime)).resolves.toBeNull();
    await expect(getOfflineCalendarPayload(13, 7, validationTime)).resolves.toMatchObject({
      payload: { event_id: 7, event_name: "Other", tasks: [], persons: [] },
    });
  });

  it("does not fall back to localStorage when IndexedDB is unavailable", async () => {
    disableIndexedDb();

    await expect(
      storeOfflineCalendarPayload(12, 7, payload, cachedAt, validUntil, validationTime),
    ).rejects.toMatchObject({ code: "storage_unavailable" });
    await expect(getOfflineCalendarPayload(12, 7, validationTime)).rejects.toMatchObject({
      code: "storage_unavailable",
    });
    expect(localStorage.length).toBe(2);
  });
});
