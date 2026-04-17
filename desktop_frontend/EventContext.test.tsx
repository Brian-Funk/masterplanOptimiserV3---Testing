/**
 * Tests for desktop EventContext — event selection and fetching.
 */
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor, act } from "@testing-library/react";
import React from "react";

// Mock environment
vi.mock("@/lib/environment", () => ({
  getApiUrl: () => "http://127.0.0.1:8000",
  isDesktopApp: () => true,
}));

const mockFetch = vi.fn();
vi.stubGlobal("fetch", mockFetch);

import { EventProvider, useEvent } from "@/contexts/EventContext";

const EVENTS = [
  {
    id: 1,
    name: "Lucerne 2026",
    location: "Lucerne",
    start_date: "2026-08-01",
    end_date: "2026-08-14",
  },
  {
    id: 2,
    name: "Zurich 2026",
    location: "Zurich",
    start_date: "2026-09-01",
    end_date: "2026-09-10",
  },
];

function EventConsumer() {
  const {
    selectedEventId,
    setSelectedEventId,
    availableEvents,
    isLoadingEvents,
  } = useEvent();
  return (
    <div>
      <span data-testid="loading">{String(isLoadingEvents)}</span>
      <span data-testid="selected">{selectedEventId ?? "none"}</span>
      <span data-testid="count">{availableEvents.length}</span>
      <ul>
        {availableEvents.map((e) => (
          <li key={e.id} data-testid={`event-${e.id}`}>
            {e.name}
          </li>
        ))}
      </ul>
      <button onClick={() => setSelectedEventId(1)}>Select 1</button>
      <button onClick={() => setSelectedEventId(null)}>Clear</button>
    </div>
  );
}

beforeEach(() => {
  mockFetch.mockReset();
  sessionStorage.clear();
});

describe("EventContext", () => {
  it("fetches events on mount", async () => {
    mockFetch.mockResolvedValue({ ok: true, json: async () => EVENTS });

    render(
      <EventProvider>
        <EventConsumer />
      </EventProvider>,
    );

    await waitFor(() => {
      expect(screen.getByTestId("count")).toHaveTextContent("2");
    });
    expect(screen.getByTestId("event-1")).toHaveTextContent("Lucerne 2026");
    expect(screen.getByTestId("event-2")).toHaveTextContent("Zurich 2026");
  });

  it("starts with no selection", async () => {
    mockFetch.mockResolvedValue({ ok: true, json: async () => EVENTS });

    render(
      <EventProvider>
        <EventConsumer />
      </EventProvider>,
    );

    await waitFor(() => {
      expect(screen.getByTestId("count")).toHaveTextContent("2");
    });
    expect(screen.getByTestId("selected")).toHaveTextContent("none");
  });

  it("selects an event and persists to sessionStorage", async () => {
    mockFetch.mockResolvedValue({ ok: true, json: async () => EVENTS });

    render(
      <EventProvider>
        <EventConsumer />
      </EventProvider>,
    );

    await waitFor(() => {
      expect(screen.getByTestId("count")).toHaveTextContent("2");
    });

    act(() => {
      screen.getByText("Select 1").click();
    });

    expect(screen.getByTestId("selected")).toHaveTextContent("1");
    expect(sessionStorage.getItem("masterplan_selected_event_id")).toBe("1");
  });

  it("clears selection and removes from sessionStorage", async () => {
    sessionStorage.setItem("masterplan_selected_event_id", "1");
    mockFetch.mockResolvedValue({ ok: true, json: async () => EVENTS });

    render(
      <EventProvider>
        <EventConsumer />
      </EventProvider>,
    );

    await waitFor(() => {
      expect(screen.getByTestId("count")).toHaveTextContent("2");
    });

    act(() => {
      screen.getByText("Clear").click();
    });

    expect(screen.getByTestId("selected")).toHaveTextContent("none");
    expect(sessionStorage.getItem("masterplan_selected_event_id")).toBeNull();
  });

  it("handles fetch failure gracefully", async () => {
    mockFetch.mockRejectedValue(new Error("Network error"));
    const spy = vi.spyOn(console, "error").mockImplementation(() => {});

    render(
      <EventProvider>
        <EventConsumer />
      </EventProvider>,
    );

    await waitFor(() => {
      expect(screen.getByTestId("loading")).toHaveTextContent("false");
    });
    expect(screen.getByTestId("count")).toHaveTextContent("0");
    spy.mockRestore();
  });

  it("clears stale selection when event no longer exists", async () => {
    sessionStorage.setItem("masterplan_selected_event_id", "999");
    mockFetch.mockResolvedValue({ ok: true, json: async () => EVENTS });

    render(
      <EventProvider>
        <EventConsumer />
      </EventProvider>,
    );

    await waitFor(() => {
      expect(screen.getByTestId("count")).toHaveTextContent("2");
    });
    // The stale selection (999) should be cleared since that event doesn't exist
    expect(screen.getByTestId("selected")).toHaveTextContent("none");
  });
});

describe("useEvent outside provider", () => {
  it("throws when used outside EventProvider", () => {
    const spy = vi.spyOn(console, "error").mockImplementation(() => {});
    function Bare() {
      useEvent();
      return null;
    }
    expect(() => render(<Bare />)).toThrow(
      "useEvent must be used within an EventProvider",
    );
    spy.mockRestore();
  });
});
