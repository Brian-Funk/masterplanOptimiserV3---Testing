/**
 * Tests for ToastContext — notification management.
 */
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, act, fireEvent } from "@testing-library/react";
import React from "react";
import { ToastProvider, useToast } from "@/contexts/ToastContext";

function ToastConsumer() {
  const { toasts, addToast, removeToast } = useToast();
  return (
    <div>
      <button onClick={() => addToast("Hello", "success")}>Add</button>
      <button onClick={() => addToast("Oops", "error")}>Error</button>
      <ul>
        {toasts.map((t) => (
          <li key={t.id} data-testid={`toast-${t.id}`}>
            {t.variant}: {t.message}
            <button onClick={() => removeToast(t.id)}>x</button>
          </li>
        ))}
      </ul>
    </div>
  );
}

function renderWithToast() {
  return render(
    <ToastProvider>
      <ToastConsumer />
    </ToastProvider>,
  );
}

beforeEach(() => {
  vi.useFakeTimers();
});

afterEach(() => {
  vi.useRealTimers();
});

describe("ToastContext", () => {
  it("adds a toast", () => {
    renderWithToast();
    fireEvent.click(screen.getByText("Add"));
    expect(screen.getByText(/success: Hello/)).toBeInTheDocument();
  });

  it("removes a toast manually", () => {
    renderWithToast();
    fireEvent.click(screen.getByText("Add"));
    expect(screen.getByText(/success: Hello/)).toBeInTheDocument();

    fireEvent.click(screen.getByText("x"));
    expect(screen.queryByText(/success: Hello/)).toBeNull();
  });

  it("auto-dismisses after 4 seconds", () => {
    renderWithToast();
    fireEvent.click(screen.getByText("Add"));
    expect(screen.getByText(/success: Hello/)).toBeInTheDocument();

    act(() => {
      vi.advanceTimersByTime(4000);
    });

    expect(screen.queryByText(/success: Hello/)).toBeNull();
  });

  it("supports multiple toasts", () => {
    renderWithToast();
    fireEvent.click(screen.getByText("Add"));
    fireEvent.click(screen.getByText("Error"));

    expect(screen.getByText(/success: Hello/)).toBeInTheDocument();
    expect(screen.getByText(/error: Oops/)).toBeInTheDocument();
  });
});

describe("useToast outside provider", () => {
  it("throws when used outside ToastProvider", () => {
    const spy = vi.spyOn(console, "error").mockImplementation(() => {});

    function Bare() {
      useToast();
      return null;
    }

    expect(() => render(<Bare />)).toThrow(
      "useToast must be used within ToastProvider",
    );

    spy.mockRestore();
  });
});
