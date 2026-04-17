/**
 * Tests for desktop ThemeContext — fetches theme from API, applies CSS vars.
 */
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import React from "react";

// Mock environment
vi.mock("@/lib/environment", () => ({
  getApiUrl: () => "http://127.0.0.1:8000",
  isDesktopApp: () => true,
}));

const mockFetch = vi.fn();
vi.stubGlobal("fetch", mockFetch);

import { ThemeProvider, useTheme } from "@/contexts/ThemeContext";

const THEME = {
  id: 1,
  name: "Default",
  is_active: true,
  primary_color_1: "#2563eb",
  primary_color_2: "#7c3aed",
  primary_color_3: "#059669",
  success_color: "#16a34a",
  warning_color: "#ca8a04",
  error_color: "#dc2626",
  info_color: "#2563eb",
  dark_mode: "light" as const,
  created_at: "2026-01-01",
  updated_at: null,
};

function ThemeConsumer() {
  const { theme, isLoading, isDark } = useTheme();
  return (
    <div>
      <span data-testid="loading">{String(isLoading)}</span>
      <span data-testid="dark">{String(isDark)}</span>
      <span data-testid="name">{theme?.name ?? "none"}</span>
      <span data-testid="primary">{theme?.primary_color_1 ?? ""}</span>
    </div>
  );
}

beforeEach(() => {
  mockFetch.mockReset();
  document.documentElement.style.cssText = "";
  document.documentElement.classList.remove("dark");
  localStorage.clear();
});

describe("ThemeContext", () => {
  it("fetches and applies theme on mount", async () => {
    mockFetch.mockResolvedValue({ ok: true, json: async () => THEME });

    render(
      <ThemeProvider>
        <ThemeConsumer />
      </ThemeProvider>,
    );

    await waitFor(() => {
      expect(screen.getByTestId("loading")).toHaveTextContent("false");
    });

    expect(screen.getByTestId("name")).toHaveTextContent("Default");
    expect(screen.getByTestId("primary")).toHaveTextContent("#2563eb");
    expect(screen.getByTestId("dark")).toHaveTextContent("false");
  });

  it("applies CSS custom properties to document root", async () => {
    mockFetch.mockResolvedValue({ ok: true, json: async () => THEME });

    render(
      <ThemeProvider>
        <ThemeConsumer />
      </ThemeProvider>,
    );

    await waitFor(() => {
      expect(screen.getByTestId("loading")).toHaveTextContent("false");
    });

    const root = document.documentElement;
    expect(root.style.getPropertyValue("--color-primary")).toBe("#2563eb");
    expect(root.style.getPropertyValue("--color-secondary")).toBe("#7c3aed");
    expect(root.style.getPropertyValue("--color-tertiary")).toBe("#059669");
    expect(root.style.getPropertyValue("--color-success")).toBe("#16a34a");
    expect(root.style.getPropertyValue("--color-warning")).toBe("#ca8a04");
    expect(root.style.getPropertyValue("--color-error")).toBe("#dc2626");
    expect(root.style.getPropertyValue("--color-info")).toBe("#2563eb");
  });

  it("applies dark class when dark_mode is dark", async () => {
    mockFetch.mockResolvedValue({
      ok: true,
      json: async () => ({ ...THEME, dark_mode: "dark" }),
    });

    render(
      <ThemeProvider>
        <ThemeConsumer />
      </ThemeProvider>,
    );

    await waitFor(() => {
      expect(screen.getByTestId("dark")).toHaveTextContent("true");
    });
    expect(document.documentElement.classList.contains("dark")).toBe(true);
  });

  it("removes dark class in light mode", async () => {
    document.documentElement.classList.add("dark");
    mockFetch.mockResolvedValue({ ok: true, json: async () => THEME });

    render(
      <ThemeProvider>
        <ThemeConsumer />
      </ThemeProvider>,
    );

    await waitFor(() => {
      expect(screen.getByTestId("dark")).toHaveTextContent("false");
    });
    expect(document.documentElement.classList.contains("dark")).toBe(false);
  });

  it("persists dark-mode preference to localStorage", async () => {
    mockFetch.mockResolvedValue({
      ok: true,
      json: async () => ({ ...THEME, dark_mode: "dark" }),
    });

    render(
      <ThemeProvider>
        <ThemeConsumer />
      </ThemeProvider>,
    );

    await waitFor(() => {
      expect(screen.getByTestId("loading")).toHaveTextContent("false");
    });
    expect(localStorage.getItem("dark-mode")).toBe("dark");
  });

  it("handles fetch failure gracefully", async () => {
    mockFetch.mockRejectedValue(new Error("Network error"));
    const spy = vi.spyOn(console, "error").mockImplementation(() => {});

    render(
      <ThemeProvider>
        <ThemeConsumer />
      </ThemeProvider>,
    );

    await waitFor(() => {
      expect(screen.getByTestId("loading")).toHaveTextContent("false");
    });
    expect(screen.getByTestId("name")).toHaveTextContent("none");
    spy.mockRestore();
  });

  it("skips secondary/tertiary when null", async () => {
    mockFetch.mockResolvedValue({
      ok: true,
      json: async () => ({
        ...THEME,
        primary_color_2: null,
        primary_color_3: null,
      }),
    });

    render(
      <ThemeProvider>
        <ThemeConsumer />
      </ThemeProvider>,
    );

    await waitFor(() => {
      expect(screen.getByTestId("loading")).toHaveTextContent("false");
    });
    const root = document.documentElement;
    // Should not have set --color-secondary or --color-tertiary
    expect(root.style.getPropertyValue("--color-secondary")).toBe("");
    expect(root.style.getPropertyValue("--color-tertiary")).toBe("");
  });
});

describe("useTheme outside provider", () => {
  it("throws when used outside ThemeProvider", () => {
    const spy = vi.spyOn(console, "error").mockImplementation(() => {});
    function Bare() {
      useTheme();
      return null;
    }
    expect(() => render(<Bare />)).toThrow(
      "useTheme must be used within a ThemeProvider",
    );
    spy.mockRestore();
  });
});
