import { render, screen, waitFor } from "@testing-library/react";
import React from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import ClientProviders from "@/app/ClientProviders";

const { mockFetch, mockPathname } = vi.hoisted(() => ({
  mockFetch: vi.fn(),
  mockPathname: vi.fn(),
}));

vi.mock("next/navigation", () => ({
  usePathname: () => mockPathname(),
}));
vi.mock("@/contexts/ThemeContext", () => ({
  ThemeProvider: ({ children }: { children: React.ReactNode }) => <>{children}</>,
}));
vi.mock("@/components/InstallPrompt", () => ({ InstallPrompt: () => null }));
vi.mock("@/lib/environment", () => ({ getApiUrl: () => "https://server.test" }));
vi.mock("@/lib/offlineCalendarCache", () => ({
  clearLegacyPrivateCaches: vi.fn().mockResolvedValue(undefined),
  clearOfflineCalendarCacheForUser: vi.fn().mockResolvedValue(undefined),
}));

describe("ClientProviders", () => {
  beforeEach(() => {
    mockFetch.mockReset();
    mockPathname.mockReset();
    vi.stubGlobal("fetch", mockFetch);
  });

  it("does not check an authenticated session on the shared schedule route", () => {
    mockPathname.mockReturnValue("/shared-schedule");

    render(
      <ClientProviders>
        <div>Shared schedule</div>
      </ClientProviders>,
    );

    expect(screen.getByText("Shared schedule")).toBeInTheDocument();
    expect(mockFetch).not.toHaveBeenCalled();
  });

  it("retains the authenticated session check on private application routes", async () => {
    mockPathname.mockReturnValue("/calendar");
    mockFetch.mockResolvedValue({ ok: false, status: 401 });

    render(
      <ClientProviders>
        <div>Calendar</div>
      </ClientProviders>,
    );

    await waitFor(() => {
      expect(mockFetch).toHaveBeenCalledWith(
        "https://server.test/api/v1/auth/me",
        { credentials: "include" },
      );
    });
  });
});
