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

// Import useAuth so we can reset it in beforeEach
import { useAuth } from "@/contexts/AuthContext";

beforeEach(() => {
  mockPush.mockReset();
  mockFetch.mockReset();
  mockRefreshUser.mockReset();
  // Reset useAuth to default unauthenticated state
  vi.mocked(useAuth).mockImplementation(() => ({
    user: null,
    isAuthenticated: false,
    isLoading: false,
    logout: vi.fn(),
    refreshUser: mockRefreshUser,
  }));
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
      const button = screen.getByRole("button", {
        name: /sign in with passkey/i,
      });
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

  it("redirects issuer with event to /calendar", async () => {
    const { useAuth } = await import("@/contexts/AuthContext");
    vi.mocked(useAuth).mockReturnValue({
      user: {
        id: 2,
        username: "issuer1",
        display_name: "Issuer One",
        email: null,
        is_root_admin: false,
        is_admin: false,
        is_issuer: true,
        can_edit: false,
        is_active: true,
        is_activated: true,
        linked_person_id: 5,
        event_id: 3,
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
      expect(mockPush).toHaveBeenCalledWith("/calendar?event=3");
    });
  });

  it("redirects regular user with event to /calendar", async () => {
    const { useAuth } = await import("@/contexts/AuthContext");
    vi.mocked(useAuth).mockReturnValue({
      user: {
        id: 3,
        username: "viewer",
        display_name: "Viewer",
        email: null,
        is_root_admin: false,
        is_admin: false,
        is_issuer: false,
        can_edit: false,
        is_active: true,
        is_activated: true,
        linked_person_id: null,
        event_id: 2,
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
      expect(mockPush).toHaveBeenCalledWith("/calendar?event=2");
    });
  });

  it("redirects user without event to /admin", async () => {
    const { useAuth } = await import("@/contexts/AuthContext");
    vi.mocked(useAuth).mockReturnValue({
      user: {
        id: 4,
        username: "noevent",
        display_name: "No Event",
        email: null,
        is_root_admin: false,
        is_admin: false,
        is_issuer: false,
        can_edit: false,
        is_active: true,
        is_activated: true,
        linked_person_id: null,
        event_id: null,
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

  it("shows heading and subtitle", async () => {
    mockFetch.mockResolvedValue({
      ok: true,
      json: async () => ({ needs_bootstrap: false }),
    });

    const { default: LoginPage } = await import("@/app/login/page");
    render(<LoginPage />);

    await waitFor(() => {
      expect(screen.getByText("Masterplan Optimiser")).toBeInTheDocument();
      expect(screen.getByText("Sign in to your account")).toBeInTheDocument();
    });
  });

  it("button is not disabled by default", async () => {
    mockFetch.mockResolvedValue({
      ok: true,
      json: async () => ({ needs_bootstrap: false }),
    });

    const { default: LoginPage } = await import("@/app/login/page");
    render(<LoginPage />);

    await waitFor(() => {
      const button = screen.getByRole("button", {
        name: /sign in with passkey/i,
      });
      expect(button).not.toBeDisabled();
    });
  });

  it("stays on login when bootstrap check fails", async () => {
    mockFetch.mockRejectedValue(new Error("Network error"));

    const { default: LoginPage } = await import("@/app/login/page");
    render(<LoginPage />);

    // Should not redirect — stays on login
    await waitFor(() => {
      expect(
        screen.getByRole("button", { name: /sign in with passkey/i }),
      ).toBeInTheDocument();
    });
    expect(mockPush).not.toHaveBeenCalled();
  });
});
