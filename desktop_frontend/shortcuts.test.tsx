import React from "react";
import { describe, it, expect, beforeEach, vi } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import {
  SHORTCUT_DEFINITIONS,
  detectShortcutConflicts,
  resolveShortcutBindings,
  shortcutFromKeyboardEvent,
} from "@/lib/shortcuts";
import { ShortcutProvider } from "@/contexts/ShortcutContext";
import { ShortcutSettingsSection } from "@/app/dashboard/settings/components/ShortcutSettingsSection";

describe("desktop shortcut registry", () => {
  it("includes defaults for metrics, presentation, and publish shortcuts", () => {
    const bindings = resolveShortcutBindings({});

    expect(bindings["optimised.openMetrics"]).toBe("Ctrl+M");
    expect(bindings["optimised.openPresentation"]).toBe("Ctrl+P");
    expect(bindings["optimised.publishDay"]).toBe("Ctrl+Enter");
    expect(bindings["optimised.publishAllDays"]).toBe("Ctrl+Shift+Enter");
  });

  it("detects duplicate bindings in the same shortcut scope", () => {
    const bindings = resolveShortcutBindings({
      "optimised.openPresentation": "Ctrl+M",
    });

    const conflicts = detectShortcutConflicts(bindings);
    expect(conflicts.get("optimised.openMetrics")?.[0]?.id).toBe(
      "optimised.openPresentation",
    );
    expect(conflicts.get("optimised.openPresentation")?.[0]?.id).toBe(
      "optimised.openMetrics",
    );
  });

  it("captures key combinations from keyboard events", () => {
    const event = new KeyboardEvent("keydown", {
      key: "Enter",
      ctrlKey: true,
      shiftKey: true,
    });

    expect(shortcutFromKeyboardEvent(event)).toBe("Ctrl+Shift+Enter");
  });

  it("TEMPORARY_FAIL_BRANCH_PROTECTION_SHORTCUTS", () => {
    expect("remove this temporary failure before merge").toBe(
      "branch protection should block this merge",
    );
  });
});

describe("ShortcutSettingsSection", () => {
  let savedPayload: unknown;

  beforeEach(() => {
    savedPayload = undefined;
    vi.restoreAllMocks();
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
        const url = String(input);
        const method = init?.method || "GET";

        if (url.includes("/api/v1/app-settings/shortcuts")) {
          if (method === "GET") {
            return new Response(JSON.stringify({ shortcuts: {} }), {
              status: 200,
              headers: { "Content-Type": "application/json" },
            });
          }
          if (method === "PUT") {
            savedPayload = JSON.parse(String(init?.body || "{}"));
            return new Response(JSON.stringify(savedPayload), {
              status: 200,
              headers: { "Content-Type": "application/json" },
            });
          }
          if (method === "DELETE") {
            return new Response(JSON.stringify({ status: "success" }), {
              status: 200,
              headers: { "Content-Type": "application/json" },
            });
          }
        }

        return new Response(JSON.stringify({}), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        });
      }),
    );
  });

  function renderShortcuts() {
    return render(
      <ShortcutProvider>
        <ShortcutSettingsSection />
      </ShortcutProvider>,
    );
  }

  it("updates a shortcut binding through inline key capture", async () => {
    renderShortcuts();

    await screen.findByText("Open Metrics Board");
    fireEvent.click(screen.getByLabelText("Edit Open Metrics Board"));
    fireEvent.keyDown(
      screen.getByTestId("shortcut-capture-optimised.openMetrics"),
      {
        key: "L",
        ctrlKey: true,
      },
    );

    expect(
      screen.getByTestId("shortcut-binding-optimised.openMetrics"),
    ).toHaveTextContent("Ctrl+L");
  });

  it("shows conflict text for duplicate same-scope bindings", async () => {
    renderShortcuts();

    await screen.findByText("Open Presentation");
    fireEvent.click(screen.getByLabelText("Edit Open Presentation"));
    fireEvent.keyDown(
      screen.getByTestId("shortcut-capture-optimised.openPresentation"),
      {
        key: "M",
        ctrlKey: true,
      },
    );

    expect(
      screen.getByTestId("shortcut-conflict-optimised.openPresentation"),
    ).toHaveTextContent("Conflicts with: Open Metrics Board");
  });

  it("saves shortcut overrides through the app settings API", async () => {
    renderShortcuts();

    await screen.findByText("Open Metrics Board");
    fireEvent.click(screen.getByLabelText("Edit Open Metrics Board"));
    fireEvent.keyDown(
      screen.getByTestId("shortcut-capture-optimised.openMetrics"),
      {
        key: "L",
        ctrlKey: true,
      },
    );
    fireEvent.click(screen.getByText("Save changes"));

    await waitFor(() =>
      expect(savedPayload).toEqual({
        shortcuts: {
          "optimised.openMetrics": "Ctrl+L",
        },
      }),
    );
  });

  it("keeps every shortcut id unique in the registry", () => {
    const ids = SHORTCUT_DEFINITIONS.map((definition) => definition.id);
    expect(new Set(ids).size).toBe(ids.length);
  });
});
