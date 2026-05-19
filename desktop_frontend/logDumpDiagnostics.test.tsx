import React from "react";
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { LogDumpErrorBoundary } from "@/components/LogDumpErrorBoundary";
import {
  isLogDumpAvailable,
  normaliseErrorForLog,
  recordRendererError,
  saveLogDump,
} from "@/lib/electronDiagnostics";

function installElectronBridge() {
  const bridge = {
    isElectron: true,
    saveLogDump: vi.fn(async () => ({ success: true, path: "log.txt" })),
    recordRendererError: vi.fn(async () => ({ success: true })),
  };
  Object.defineProperty(window, "electron", {
    configurable: true,
    value: bridge,
  });
  return bridge;
}

function ThrowingChild() {
  throw new Error("Diagnostic test crash");
}

describe("desktop log dump diagnostics", () => {
  beforeEach(() => {
    installElectronBridge();
  });

  afterEach(() => {
    vi.restoreAllMocks();
    Reflect.deleteProperty(window, "electron");
  });

  it("detects when the Electron log dump bridge is available", () => {
    expect(isLogDumpAvailable()).toBe(true);
  });

  it("normalises thrown values for renderer logging", () => {
    const error = new Error("Special character name: Fran\u010di\u0161ka");
    const normalised = normaliseErrorForLog(error);

    expect(normalised.message).toBe("Special character name: Fran\u010di\u0161ka");
    expect(normalised.stack).toContain("Special character name");
  });

  it("forwards renderer errors to the Electron diagnostics bridge", async () => {
    const bridge = installElectronBridge();

    await recordRendererError("unit-test", new Error("Renderer failed"), {
      route: "/dashboard",
    });

    expect(bridge.recordRendererError).toHaveBeenCalledWith(
      expect.objectContaining({
        source: "unit-test",
        message: "Renderer failed",
        extra: JSON.stringify({ route: "/dashboard" }),
      }),
    );
  });

  it("asks Electron to save a text log dump with the selected reason", async () => {
    const bridge = installElectronBridge();

    const result = await saveLogDump("Manual diagnostic log dump", "About page");

    expect(result.success).toBe(true);
    expect(bridge.saveLogDump).toHaveBeenCalledWith({
      reason: "Manual diagnostic log dump",
      detail: "About page",
    });
  });

  it("shows an error page that explains how to use a log dump", async () => {
    const consoleSpy = vi.spyOn(console, "error").mockImplementation(() => {});

    render(
      <LogDumpErrorBoundary>
        <ThrowingChild />
      </LogDumpErrorBoundary>,
    );

    expect(screen.getByText("Something went wrong")).toBeInTheDocument();
    expect(
      screen.getByText(/forward it to the developer so they can analyse/i),
    ).toBeInTheDocument();
    expect(screen.getByText("Diagnostic test crash")).toBeInTheDocument();

    consoleSpy.mockRestore();
  });

  it("downloads a log dump from the React error fallback", async () => {
    const bridge = installElectronBridge();
    const consoleSpy = vi.spyOn(console, "error").mockImplementation(() => {});

    render(
      <LogDumpErrorBoundary>
        <ThrowingChild />
      </LogDumpErrorBoundary>,
    );

    fireEvent.click(screen.getByText("Download Log Dump"));

    await waitFor(() => {
      expect(bridge.saveLogDump).toHaveBeenCalledWith({
        reason: "Renderer error",
        detail: "Diagnostic test crash",
      });
    });
    expect(screen.getByText("Log dump saved.")).toBeInTheDocument();

    consoleSpy.mockRestore();
  });
});
