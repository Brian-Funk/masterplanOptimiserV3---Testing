/** Tests for IndexedDB-only offline calendar payload storage. */
import { beforeEach, describe, expect, it } from "vitest";
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
          });
          return request;
        },
        openCursor: () => {
          const request: Record<string, unknown> = {};
          const keys = Array.from(records.keys());
          let index = 0;
          const emit = () => {
            queueMicrotask(() => {
              if (index >= keys.length) {
                request.result = null;
                (request.onsuccess as (() => void) | undefined)?.();
                queueMicrotask(() =>
                  (transaction.oncomplete as (() => void) | undefined)?.(),
                );
                return;
              }
              const key = keys[index];
              request.result = {
                value: records.get(key),
                delete: () => records.delete(key),
                continue: () => {
                  index += 1;
                  emit();
                },
              };
              (request.onsuccess as (() => void) | undefined)?.();
            });
          };
          emit();
          return request;
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
});

describe("offlineCalendarCache", () => {
  it("stores and reads a payload for the same user and event", async () => {
    await storeOfflineCalendarPayload(
      12,
      7,
      payload,
      "2026-05-21T09:30:00.000Z",
    );

    await expect(getOfflineCalendarPayload<typeof payload>(12, 7)).resolves.toMatchObject({
      user_id: 12,
      event_id: 7,
      cached_at: "2026-05-21T09:30:00.000Z",
      payload,
    });
    expect(localStorage.length).toBe(0);
  });

  it("does not return another user or event's payload", async () => {
    await storeOfflineCalendarPayload(12, 7, payload);

    await expect(getOfflineCalendarPayload(13, 7)).resolves.toBeNull();
    await expect(getOfflineCalendarPayload(12, 8)).resolves.toBeNull();
  });

  it("clears cached payloads for only the selected user", async () => {
    await storeOfflineCalendarPayload(12, 7, payload);
    await storeOfflineCalendarPayload(13, 7, { event_name: "Other" });

    await clearOfflineCalendarCacheForUser(12);

    await expect(getOfflineCalendarPayload(12, 7)).resolves.toBeNull();
    await expect(getOfflineCalendarPayload(13, 7)).resolves.toMatchObject({
      payload: { event_name: "Other" },
    });
  });

  it("does not fall back to localStorage when IndexedDB is unavailable", async () => {
    disableIndexedDb();

    await expect(storeOfflineCalendarPayload(12, 7, payload)).resolves.toMatchObject({
      user_id: 12,
      event_id: 7,
    });
    await expect(getOfflineCalendarPayload(12, 7)).resolves.toBeNull();
    expect(localStorage.length).toBe(0);
  });
});
