/**
 * Tests for the root route redirect behaviour.
 */
import { beforeEach, describe, expect, it, vi } from "vitest";
import { render, waitFor } from "@testing-library/react";
import React from "react";

const mockPush = vi.hoisted(() => vi.fn());

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: mockPush }),
}));

function storeOfflineMarker(validUntil: string): void {
  localStorage.setItem(
    "mp-opt-offline-access",
    JSON.stringify({
      user_id: 42,
      event_id: 9,
      cached_at: "2026-05-21T09:30:00.000Z",
      valid_until: validUntil,
      ttl_hours: 24,
    }),
  );
}

describe("HomePage", () => {
  beforeEach(() => {
    mockPush.mockReset();
    localStorage.clear();
  });

  it("redirects to the cached calendar route when offline access is valid", async () => {
    storeOfflineMarker("2999-05-21T23:59:59.999Z");

    const { default: HomePage } = await import("@/app/page");
    render(<HomePage />);

    await waitFor(() => {
      expect(mockPush).toHaveBeenCalledWith("/calendar?event=9");
    });
  });

  it("redirects to login when no valid offline marker exists", async () => {
    const { default: HomePage } = await import("@/app/page");
    render(<HomePage />);

    await waitFor(() => {
      expect(mockPush).toHaveBeenCalledWith("/login");
    });
  });

  it("redirects to login when offline access expired", async () => {
    storeOfflineMarker("2000-05-21T23:59:59.999Z");

    const { default: HomePage } = await import("@/app/page");
    render(<HomePage />);

    await waitFor(() => {
      expect(mockPush).toHaveBeenCalledWith("/login");
    });
  });
});
