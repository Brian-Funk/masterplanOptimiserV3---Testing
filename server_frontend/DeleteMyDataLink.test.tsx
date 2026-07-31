/**
 * Tests for DeleteMyDataLink component - GDPR data deletion request.
 */
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import React from "react";

// Mock environment
vi.mock("@/lib/environment", () => ({
  getApiUrl: () => "https://api.test",
}));

// Mock AuthContext
let mockIsAuthenticated = true;
vi.mock("@/contexts/AuthContext", () => ({
  useAuth: () => ({ isAuthenticated: mockIsAuthenticated }),
}));

const mockApiFetch = vi.hoisted(() => vi.fn());
vi.mock("@/lib/api", () => ({ apiFetch: mockApiFetch }));
vi.mock("@/lib/reauth", () => ({ withReauth: (operation: () => unknown) => operation() }));

// CSRF cookie
Object.defineProperty(document, "cookie", {
  writable: true,
  value: "csrf_token=test-csrf",
});

// Mock lucide-react
vi.mock("lucide-react", () => ({
  X: (props: Record<string, unknown>) =>
    React.createElement("svg", { "data-testid": "x-icon", ...props }),
  AlertTriangle: (props: Record<string, unknown>) =>
    React.createElement("svg", { "data-testid": "alert-icon", ...props }),
}));

import { DeleteMyDataLink } from "@/components/DeleteMyDataLink";

beforeEach(() => {
  mockApiFetch.mockReset();
  mockApiFetch.mockResolvedValue({ ok: false, json: async () => ({}) });
  mockIsAuthenticated = true;
});

describe("DeleteMyDataLink", () => {
  it("renders delete button when authenticated", () => {
    render(<DeleteMyDataLink />);
    expect(screen.getByText("Delete my data")).toBeInTheDocument();
  });

  it("renders nothing when not authenticated", () => {
    mockIsAuthenticated = false;
    const { container } = render(<DeleteMyDataLink />);
    expect(container.textContent).toBe("");
  });

  it("opens modal on click", async () => {
    const user = userEvent.setup();
    render(<DeleteMyDataLink />);

    await user.click(screen.getByText("Delete my data"));

    expect(screen.getByText("Request Data Deletion")).toBeInTheDocument();
    expect(screen.getByText(/GDPR Article 17/)).toBeInTheDocument();
  });

  it("modal has cancel and submit buttons", async () => {
    const user = userEvent.setup();
    render(<DeleteMyDataLink />);

    await user.click(screen.getByText("Delete my data"));

    expect(screen.getByText("Cancel")).toBeInTheDocument();
    expect(screen.getByText("Submit Deletion Request")).toBeInTheDocument();
  });

  it("closes modal on cancel", async () => {
    const user = userEvent.setup();
    render(<DeleteMyDataLink />);

    await user.click(screen.getByText("Delete my data"));
    expect(screen.getByText("Request Data Deletion")).toBeInTheDocument();

    await user.click(screen.getByText("Cancel"));
    expect(screen.queryByText("Request Data Deletion")).toBeNull();
  });

  it("closes modal on close button", async () => {
    const user = userEvent.setup();
    render(<DeleteMyDataLink />);

    await user.click(screen.getByText("Delete my data"));
    expect(screen.getByText("Request Data Deletion")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: /close/i }));
    expect(screen.queryByText("Request Data Deletion")).toBeNull();
  });

  it("submits deletion request successfully", async () => {
    mockApiFetch.mockImplementation((_url, init) =>
      init?.method === "POST"
        ? Promise.resolve({
            ok: true,
            json: async () => ({
              request_id: "request-1",
              state: "submitted",
              submitted_at: "2026-07-31T10:00:00Z",
              normal_response_due_at: "2026-08-30T10:00:00Z",
            }),
          })
        : Promise.resolve({ ok: false, json: async () => ({}) }),
    );

    const user = userEvent.setup();
    render(<DeleteMyDataLink />);

    await user.click(screen.getByText("Delete my data"));
    await user.click(screen.getByText("Submit Deletion Request"));

    await waitFor(() => {
      expect(screen.getByText("Deletion request")).toBeInTheDocument();
      expect(screen.getByTestId("deletion-request-id")).toHaveTextContent("request-1");
    });
  });

  it("shows error on failed submission", async () => {
    mockApiFetch.mockImplementation((_url, init) => Promise.resolve(
      init?.method === "POST"
        ? { ok: false, json: async () => ({ detail: "Already requested" }) }
        : { ok: false, json: async () => ({}) },
    ));

    const user = userEvent.setup();
    render(<DeleteMyDataLink />);

    await user.click(screen.getByText("Delete my data"));
    await user.click(screen.getByText("Submit Deletion Request"));

    await waitFor(() => {
      expect(screen.getByText("Already requested")).toBeInTheDocument();
    });
  });

  it("shows generic error when response has no detail", async () => {
    mockApiFetch.mockImplementation((_url, init) => Promise.resolve(
      init?.method === "POST"
        ? { ok: false, json: async () => { throw new Error("no json"); } }
        : { ok: false, json: async () => ({}) },
    ));

    const user = userEvent.setup();
    render(<DeleteMyDataLink />);

    await user.click(screen.getByText("Delete my data"));
    await user.click(screen.getByText("Submit Deletion Request"));

    await waitFor(() => {
      expect(
        screen.getByText("Something went wrong. Please try again."),
      ).toBeInTheDocument();
    });
  });

  it("shows network error message", async () => {
    mockApiFetch.mockImplementation((_url, init) =>
      init?.method === "POST"
        ? Promise.reject(new Error("Network error"))
        : Promise.resolve({ ok: false, json: async () => ({}) }),
    );

    const user = userEvent.setup();
    render(<DeleteMyDataLink />);

    await user.click(screen.getByText("Delete my data"));
    await user.click(screen.getByText("Submit Deletion Request"));

    await waitFor(() => {
      expect(
        screen.getByText("Network error. Please try again."),
      ).toBeInTheDocument();
    });
  });

  it("shows loading state during submission", async () => {
    // Never-resolving fetch to keep loading state
    mockApiFetch.mockImplementation((_url, init) =>
      init?.method === "POST"
        ? new Promise(() => {})
        : Promise.resolve({ ok: false, json: async () => ({}) }),
    );

    const user = userEvent.setup();
    render(<DeleteMyDataLink />);

    await user.click(screen.getByText("Delete my data"));
    await user.click(screen.getByText("Submit Deletion Request"));

    await waitFor(() => {
      expect(screen.getByText("Submitting...")).toBeInTheDocument();
    });
  });

  it("displays explanation steps in the modal", async () => {
    const user = userEvent.setup();
    render(<DeleteMyDataLink />);

    await user.click(screen.getByText("Delete my data"));

    expect(screen.getByText(/administrator is notified/)).toBeInTheDocument();
    expect(screen.getByText(/matching desktop person record are deleted/)).toBeInTheDocument();
    expect(screen.getByText(/cannot be completed while any required deletion remains unresolved/)).toBeInTheDocument();
  });
});
