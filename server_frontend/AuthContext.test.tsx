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
