import React from "react";
import { describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";
import { EventStatusBar } from "@/app/dashboard/admin/components/EventStatusBar";
import {
  countManualEdits,
  deriveEventStatusSummary,
} from "@/lib/eventStatusSummary";

const optimisedSchedule = {
  start_time: 600,
  end_time: 660,
  location: 1,
  assigned_persons: [10],
};

describe("event status confidence summary", () => {
  it("counts manual edits when final schedule differs from optimiser output", () => {
    expect(
      countManualEdits([
        {
          optimised: optimisedSchedule,
          final: { ...optimisedSchedule },
        },
        {
          optimised: optimisedSchedule,
          final: { ...optimisedSchedule, end_time: 690 },
        },
      ] as any),
    ).toBe(1);
  });

  it("summarises review state for published schedules with pending manual edits", () => {
    const summary = deriveEventStatusSummary({
      eventStatus: "published",
      personCount: 3,
      locationCount: 2,
      publishTarget: "google",
      taskInstances: [
        {
          optimised: optimisedSchedule,
          final: { ...optimisedSchedule, start_time: 630 },
        },
      ] as any,
      jobs: [
        {
          id: 1,
          date: "2026-08-01",
          status: "completed",
          is_test_run: false,
          created_at: "2026-08-01T10:00:00Z",
        },
      ],
    });

    expect(summary.headline).toBe("Review before publishing");
    expect(summary.primary).toMatchObject({
      title: "Event changes pending",
      level: "review",
      actionId: "manualChanges",
      description: "1 manual edit across the full schedule.",
    });
    expect(summary.items.find((item) => item.id === "setup")).toMatchObject({
      status: "Ready",
      level: "ready",
    });
    expect(
      summary.items.find((item) => item.id === "manualChanges"),
    ).toMatchObject({
      status: "1 edit",
      level: "review",
    });
    expect(
      summary.items.find((item) => item.id === "publishing"),
    ).toMatchObject({
      status: "Changes pending",
      level: "review",
    });
  });

  it("uses conservative states when setup and publish target are missing", () => {
    const summary = deriveEventStatusSummary({
      eventStatus: "draft",
      personCount: 0,
      locationCount: 0,
      publishTarget: "none",
      taskInstances: [],
      jobs: [],
    });

    expect(summary.headline).toBe("Action needed");
    expect(summary.primary).toMatchObject({
      title: "Event setup not started",
      level: "review",
      actionId: "setup",
    });
    expect(summary.items.find((item) => item.id === "setup")).toMatchObject({
      status: "Not started",
      level: "unknown",
    });
    expect(
      summary.items.find((item) => item.id === "publishing"),
    ).toMatchObject({
      status: "No target",
      level: "blocked",
    });
  });
});

describe("EventStatusBar", () => {
  it("renders compact status items and optional actions", () => {
    const configure = vi.fn();
    const summary = deriveEventStatusSummary({
      eventStatus: "draft",
      personCount: 1,
      locationCount: 1,
      publishTarget: "none",
      taskInstances: [
        {
          optimised: optimisedSchedule,
          final: { ...optimisedSchedule },
        },
      ] as any,
      jobs: [],
    });

    render(
      <EventStatusBar
        summary={summary}
        actions={{ publishing: { label: "Configure", onClick: configure } }}
      />,
    );

    expect(
      screen.getByRole("region", { name: "Event status summary" }),
    ).toBeInTheDocument();
    expect(screen.getByTestId("event-status-headline")).toHaveTextContent(
      "Event publishing not configured",
    );
    expect(screen.getByText("Configure")).toBeInTheDocument();

    fireEvent.click(screen.getByText("Details"));

    expect(screen.getByTestId("event-status-item-setup")).toHaveTextContent(
      "Setup",
    );
    expect(
      screen.getByTestId("event-status-item-optimisation"),
    ).toHaveTextContent("Ready");
    expect(
      screen.getByTestId("event-status-item-publishing"),
    ).toHaveTextContent("No target");
  });
});
