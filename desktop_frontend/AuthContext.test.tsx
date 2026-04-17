/**
 * Tests for desktop AuthContext — static local user, no login needed.
 */
import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import React from "react";
import { AuthProvider, useAuth } from "@/contexts/AuthContext";

function AuthConsumer() {
  const { user, isLoading } = useAuth();
  return (
    <div>
      <span data-testid="id">{user.id}</span>
      <span data-testid="username">{user.username}</span>
      <span data-testid="email">{user.email}</span>
      <span data-testid="loading">{String(isLoading)}</span>
    </div>
  );
}

describe("AuthContext", () => {
  it("provides a static local user", () => {
    render(
      <AuthProvider>
        <AuthConsumer />
      </AuthProvider>,
    );
    expect(screen.getByTestId("id")).toHaveTextContent("0");
    expect(screen.getByTestId("username")).toHaveTextContent("local");
    expect(screen.getByTestId("email")).toHaveTextContent("");
  });

  it("isLoading is always false", () => {
    render(
      <AuthProvider>
        <AuthConsumer />
      </AuthProvider>,
    );
    expect(screen.getByTestId("loading")).toHaveTextContent("false");
  });

  it("works without a provider (uses default context value)", () => {
    render(<AuthConsumer />);
    expect(screen.getByTestId("username")).toHaveTextContent("local");
  });
});
