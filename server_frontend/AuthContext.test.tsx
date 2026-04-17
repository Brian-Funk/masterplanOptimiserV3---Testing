/**
 * Tests for AuthContext — authentication state management.
 */
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor, act } from "@testing-library/react";
import React from "react";
import { AuthProvider, useAuth } from "@/contexts/AuthContext";

// Mock fetch globally
const mockFetch = vi.fn();
vi.stubGlobal("fetch", mockFetch);

// Helper component that displays auth state
function AuthConsumer() {
  const { user, isAuthenticated, isLoading } = useAuth();
  if (isLoading) return <div>Loading...</div>;
  if (!isAuthenticated) return <div>Not authenticated</div>;
  return (
    <div>
      <span data-testid="username">{user!.username}</span>
      <span data-testid="role">
        {user!.is_admin ? "admin" : user!.is_issuer ? "issuer" : "user"}
      </span>
    </div>
  );
}

function renderWithAuth() {
  return render(
    <AuthProvider>
      <AuthConsumer />
    </AuthProvider>,
  );
}

const mockUser = {
  id: 1,
  username: "testadmin",
  display_name: "Test Admin",
  email: "admin@test.com",
  is_root_admin: false,
  is_admin: true,
  is_issuer: false,
  can_edit: true,
  is_active: true,
  is_activated: true,
  linked_person_id: null,
  event_id: 1,
};

beforeEach(() => {
  mockFetch.mockReset();
});

describe("AuthContext", () => {
  it("shows loading state initially", () => {
    mockFetch.mockImplementation(() => new Promise(() => {})); // never resolves
    renderWithAuth();
    expect(screen.getByText("Loading...")).toBeInTheDocument();
  });

  it("sets user when /auth/me returns 200", async () => {
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: async () => mockUser,
    });

    renderWithAuth();

    await waitFor(() => {
      expect(screen.getByTestId("username")).toHaveTextContent("testadmin");
    });
    expect(screen.getByTestId("role")).toHaveTextContent("admin");
  });

  it("sets user to null when /auth/me returns 401", async () => {
    mockFetch.mockResolvedValueOnce({ ok: false, status: 401 });

    renderWithAuth();

    await waitFor(() => {
      expect(screen.getByText("Not authenticated")).toBeInTheDocument();
    });
  });

  it("handles fetch error gracefully", async () => {
    mockFetch.mockRejectedValueOnce(new Error("Network error"));

    renderWithAuth();

    await waitFor(() => {
      expect(screen.getByText("Not authenticated")).toBeInTheDocument();
    });
  });

  it("identifies issuer role correctly", async () => {
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({
        ...mockUser,
        is_admin: false,
        is_issuer: true,
      }),
    });

    renderWithAuth();

    await waitFor(() => {
      expect(screen.getByTestId("role")).toHaveTextContent("issuer");
    });
  });

  it("identifies root admin correctly", async () => {
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({
        ...mockUser,
        is_root_admin: true,
        is_admin: true,
      }),
    });

    renderWithAuth();

    await waitFor(() => {
      expect(screen.getByTestId("username")).toHaveTextContent("testadmin");
      expect(screen.getByTestId("role")).toHaveTextContent("admin");
    });
  });

  it("identifies regular user correctly", async () => {
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({
        ...mockUser,
        is_admin: false,
        is_issuer: false,
      }),
    });

    renderWithAuth();

    await waitFor(() => {
      expect(screen.getByTestId("role")).toHaveTextContent("user");
    });
  });
});

describe("AuthContext logout", () => {
  it("sets user to null after logout", async () => {
    // First call: /auth/me returns a user
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: async () => mockUser,
    });
    // Second call: /auth/logout
    mockFetch.mockResolvedValueOnce({ ok: true });

    function LogoutConsumer() {
      const { user, isAuthenticated, isLoading, logout } = useAuth();
      if (isLoading) return <div>Loading...</div>;
      return (
        <div>
          <span data-testid="auth">{isAuthenticated ? "yes" : "no"}</span>
          <button onClick={logout}>Logout</button>
        </div>
      );
    }

    render(
      <AuthProvider>
        <LogoutConsumer />
      </AuthProvider>,
    );

    await waitFor(() => {
      expect(screen.getByTestId("auth")).toHaveTextContent("yes");
    });

    await act(async () => {
      screen.getByText("Logout").click();
    });

    await waitFor(() => {
      expect(screen.getByTestId("auth")).toHaveTextContent("no");
    });
  });

  it("calls /auth/logout endpoint with POST", async () => {
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: async () => mockUser,
    });
    mockFetch.mockResolvedValueOnce({ ok: true });

    function LogoutConsumer() {
      const { isLoading, logout } = useAuth();
      if (isLoading) return <div>Loading...</div>;
      return <button onClick={logout}>Logout</button>;
    }

    render(
      <AuthProvider>
        <LogoutConsumer />
      </AuthProvider>,
    );

    await waitFor(() => {
      expect(screen.getByText("Logout")).toBeInTheDocument();
    });

    await act(async () => {
      screen.getByText("Logout").click();
    });

    // Second fetch call should be the logout POST
    const logoutCall = mockFetch.mock.calls[1];
    expect(logoutCall[0]).toContain("/api/v1/auth/logout");
    expect(logoutCall[1].method).toBe("POST");
    expect(logoutCall[1].credentials).toBe("include");
  });

  it("handles logout error gracefully", async () => {
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: async () => mockUser,
    });
    mockFetch.mockRejectedValueOnce(new Error("Network error"));

    function LogoutConsumer() {
      const { isAuthenticated, isLoading, logout } = useAuth();
      if (isLoading) return <div>Loading...</div>;
      return (
        <div>
          <span data-testid="auth">{isAuthenticated ? "yes" : "no"}</span>
          <button onClick={logout}>Logout</button>
        </div>
      );
    }

    const spy = vi.spyOn(console, "error").mockImplementation(() => {});

    render(
      <AuthProvider>
        <LogoutConsumer />
      </AuthProvider>,
    );

    await waitFor(() => {
      expect(screen.getByTestId("auth")).toHaveTextContent("yes");
    });

    await act(async () => {
      screen.getByText("Logout").click();
    });

    // Even on network error, user should be set to null locally
    await waitFor(() => {
      expect(screen.getByTestId("auth")).toHaveTextContent("no");
    });

    spy.mockRestore();
  });

  it("refreshUser re-fetches and updates context", async () => {
    // Initial fetch: user is admin
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: async () => mockUser,
    });

    function RefreshConsumer() {
      const { user, isLoading, refreshUser } = useAuth();
      if (isLoading) return <div>Loading...</div>;
      return (
        <div>
          <span data-testid="name">{user?.display_name || "none"}</span>
          <button onClick={refreshUser}>Refresh</button>
        </div>
      );
    }

    render(
      <AuthProvider>
        <RefreshConsumer />
      </AuthProvider>,
    );

    await waitFor(() => {
      expect(screen.getByTestId("name")).toHaveTextContent("Test Admin");
    });

    // Set up response for refresh call
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({
        ...mockUser,
        display_name: "Updated Admin",
      }),
    });

    await act(async () => {
      screen.getByText("Refresh").click();
    });

    await waitFor(() => {
      expect(screen.getByTestId("name")).toHaveTextContent("Updated Admin");
    });
  });
});

describe("useAuth outside provider", () => {
  it("throws when used outside AuthProvider", () => {
    // Suppress React error boundary noise
    const spy = vi.spyOn(console, "error").mockImplementation(() => {});

    function Bare() {
      useAuth();
      return null;
    }

    expect(() => render(<Bare />)).toThrow(
      "useAuth must be used within an AuthProvider",
    );

    spy.mockRestore();
  });
});
