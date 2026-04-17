/**
 * Tests for ToastContainer — renders toast notifications.
 */
import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import React from "react";

// Mock lucide-react (X icon)
vi.mock("lucide-react", () => ({
  X: (props: any) => (
    <span data-testid="x-icon" {...props}>
      X
    </span>
  ),
}));

// Mock ToastContext
const mockRemoveToast = vi.fn();
vi.mock("@/contexts/ToastContext", () => ({
  useToast: vi.fn(() => ({
    toasts: [],
    removeToast: mockRemoveToast,
  })),
}));

import { useToast } from "@/contexts/ToastContext";
import { ToastContainer } from "@/components/ui/ToastContainer";

describe("ToastContainer", () => {
  it("renders nothing when there are no toasts", () => {
    vi.mocked(useToast).mockReturnValue({
      toasts: [],
      addToast: vi.fn(),
      removeToast: mockRemoveToast,
    });

    const { container } = render(<ToastContainer />);
    expect(container.innerHTML).toBe("");
  });

  it("renders a single toast", () => {
    vi.mocked(useToast).mockReturnValue({
      toasts: [{ id: 1, message: "Saved!", variant: "success" }],
      addToast: vi.fn(),
      removeToast: mockRemoveToast,
    });

    render(<ToastContainer />);
    expect(screen.getByText("Saved!")).toBeInTheDocument();
  });

  it("renders multiple toasts", () => {
    vi.mocked(useToast).mockReturnValue({
      toasts: [
        { id: 1, message: "OK", variant: "success" },
        { id: 2, message: "Error!", variant: "error" },
        { id: 3, message: "Warning", variant: "warning" },
      ],
      addToast: vi.fn(),
      removeToast: mockRemoveToast,
    });

    render(<ToastContainer />);
    expect(screen.getByText("OK")).toBeInTheDocument();
    expect(screen.getByText("Error!")).toBeInTheDocument();
    expect(screen.getByText("Warning")).toBeInTheDocument();
  });

  it("applies success variant styling", () => {
    vi.mocked(useToast).mockReturnValue({
      toasts: [{ id: 1, message: "Good", variant: "success" }],
      addToast: vi.fn(),
      removeToast: mockRemoveToast,
    });

    render(<ToastContainer />);
    const toast = screen.getByText("Good").closest("div");
    expect(toast?.className).toContain("bg-green-600");
  });

  it("applies error variant styling", () => {
    vi.mocked(useToast).mockReturnValue({
      toasts: [{ id: 1, message: "Bad", variant: "error" }],
      addToast: vi.fn(),
      removeToast: mockRemoveToast,
    });

    render(<ToastContainer />);
    const toast = screen.getByText("Bad").closest("div");
    expect(toast?.className).toContain("bg-red-600");
  });

  it("applies info variant styling", () => {
    vi.mocked(useToast).mockReturnValue({
      toasts: [{ id: 1, message: "Info", variant: "info" }],
      addToast: vi.fn(),
      removeToast: mockRemoveToast,
    });

    render(<ToastContainer />);
    const toast = screen.getByText("Info").closest("div");
    expect(toast?.className).toContain("bg-blue-600");
  });

  it("calls removeToast when dismiss button is clicked", () => {
    mockRemoveToast.mockReset();
    vi.mocked(useToast).mockReturnValue({
      toasts: [{ id: 42, message: "Dismiss me", variant: "info" }],
      addToast: vi.fn(),
      removeToast: mockRemoveToast,
    });

    render(<ToastContainer />);
    // Click the X button
    fireEvent.click(screen.getByRole("button"));
    expect(mockRemoveToast).toHaveBeenCalledWith(42);
  });
});
