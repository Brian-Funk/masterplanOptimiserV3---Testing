/**
 * Tests for the login page component.
 */
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import React from "react";

// Mock next/navigation
const mockPush = vi.fn();
vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: mockPush }),
}));

// Mock @simplewebauthn/browser
vi.mock("@simplewebauthn/browser", () => ({
  startAuthentication: vi.fn(),
}));

// Mock AuthContext
const mockRefreshUser = vi.fn();
vi.mock("@/contexts/AuthContext", () => ({
  useAuth: vi.fn(() => ({
    user: null,
    isAuthenticated: false,
    isLoading: false,
    refreshUser: mockRefreshUser,
  })),
}));

// Mock ThemeContext
vi.mock("@/contexts/ThemeContext", () => ({
  useTheme: () => ({ theme: "light", toggleTheme: vi.fn() }),
}));

// Mock fetch
const mockFetch = vi.fn();
vi.stubGlobal("fetch", mockFetch);

beforeEach(() => {
  mockPush.mockReset();
  mockFetch.mockReset();
  mockRefreshUser.mockReset();
});

describe("LoginPage", () => {
  it("renders login button", async () => {
    // Bootstrap check returns no bootstrap needed
    mockFetch.mockResolvedValue({
      ok: true,
      json: async () => ({ needs_bootstrap: false }),
    });

    // Dynamic import to allow mocks to settle
    const { default: LoginPage } = await import("@/app/login/page");
    render(<LoginPage />);

    await waitFor(() => {
      const button = screen.queryByRole("button");
      // Login page should have at least one button (Sign in with passkey)
      expect(button).toBeTruthy();
    });
  });

  it("redirects to bootstrap when needed", async () => {
    mockFetch.mockResolvedValue({
      ok: true,
      json: async () => ({ needs_bootstrap: true }),
    });

    const { default: LoginPage } = await import("@/app/login/page");
    render(<LoginPage />);

    await waitFor(() => {
      expect(mockPush).toHaveBeenCalledWith("/bootstrap");
    });
  });

  it("redirects authenticated admin to /admin", async () => {
    const { useAuth } = await import("@/contexts/AuthContext");
    vi.mocked(useAuth).mockReturnValue({
      user: {
        id: 1,
        username: "admin",
        display_name: "Admin",
        email: null,
        is_root_admin: false,
        is_admin: true,
        is_issuer: false,
        can_edit: false,
        is_active: true,
        is_activated: true,
        linked_person_id: null,
        event_id: 1,
      },
      isAuthenticated: true,
      isLoading: false,
      logout: vi.fn(),
      refreshUser: vi.fn(),
    });

    mockFetch.mockResolvedValue({
      ok: true,
      json: async () => ({ needs_bootstrap: false }),
    });

    const { default: LoginPage } = await import("@/app/login/page");
    render(<LoginPage />);

    await waitFor(() => {
      expect(mockPush).toHaveBeenCalledWith("/admin");
    });
  });
});
