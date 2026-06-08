import React from "react";
import { describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";
import Calendar from "@/components/Calendar";
import { EventStatusBar } from "@/app/dashboard/admin/components/EventStatusBar";
import {
  countManualEdits,
  detectScheduleConflicts,
  deriveEventStatusSummary,
  getScheduleFingerprint,
  getTaskChangeSummary,
} from "@/lib/eventStatusSummary";
import {
  formatStatusTimestamp,
  parseStatusTimestamp,
} from "@/lib/statusTimestamps";

const optimisedSchedule = {
  start_time: 600,
  end_time: 660,
  location: 1,
  assigned_persons: [10],
};

function publishedDayRecordsFor(tasks: any[], publishedAt = "2026-08-01T16:00:00Z") {
  const byDate = new Map<string, any[]>();
  tasks.forEach((task) => {
    if (!task.date) return;
    byDate.set(task.date, [...(byDate.get(task.date) ?? []), task]);
  });
  return Object.fromEntries(
    Array.from(byDate.entries()).map(([date, dayTasks]) => [
      date,
      {
        fingerprint: getScheduleFingerprint(dayTasks as any),
        publishedAt,
      },
    ]),
  );
}

describe("event status confidence summary", () => {
  it("formats human-readable status timestamps", () => {
    const now = new Date(2026, 7, 2, 12, 0);

    expect(formatStatusTimestamp(new Date(2026, 7, 2, 16, 0), { now })).toBe(
      "today at 16:00",
    );
    expect(formatStatusTimestamp(new Date(2026, 7, 1, 21, 35), { now })).toBe(
      "yesterday at 21:35",
    );
    expect(parseStatusTimestamp("2026-08-01T08:08:00")?.toISOString()).toBe(
      "2026-08-01T08:08:00.000Z",
    );
  });

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

  it("summarises reliable manual-change fields without flagging unrelated data", () => {
    expect(
      getTaskChangeSummary(optimisedSchedule, {
        ...optimisedSchedule,
        note: "The note changed, but scheduling did not.",
      }),
    ).toEqual([]);

    expect(
      getTaskChangeSummary(optimisedSchedule, {
        ...optimisedSchedule,
        start_time: 630,
        location: 2,
        assigned_persons: [11],
      }),
    ).toEqual(["Time changed", "Location changed", "Assignments changed"]);
  });

  it("detects person double-booking conflicts and ignores adjacent tasks", () => {
    const conflicts = detectScheduleConflicts(
      [
        {
          id: 1,
          name: "Opening",
          date: "2026-08-01",
          optimised: null,
          final: { start_time: 600, end_time: 660, assigned_persons: [10] },
        },
        {
          id: 2,
          name: "Coffee",
          date: "2026-08-01",
          optimised: null,
          final: { start_time: 630, end_time: 690, assigned_persons: [10] },
        },
        {
          id: 3,
          name: "Lunch",
          date: "2026-08-01",
          optimised: null,
          final: { start_time: 690, end_time: 720, assigned_persons: [10] },
        },
      ] as any,
      [{ id: 10, first_name: "Anna", last_name: "Test" }],
    );

    expect(conflicts).toHaveLength(1);
    expect(conflicts[0]).toMatchObject({
      type: "double_booking",
      taskIds: [1, 2],
      personIds: [10],
      message: "Anna Test is double-booked.",
    });
  });

  it("summarises review state for published schedules with pending manual edits", () => {
    const now = new Date(2026, 7, 1, 16, 30);
    const publishedTasks = [
      {
        id: 1,
        name: "Opening",
        date: "2026-08-01",
        optimised: optimisedSchedule,
        final: { ...optimisedSchedule },
      },
    ] as any;
    const summary = deriveEventStatusSummary({
      eventStatus: "published",
      personCount: 3,
      locationCount: 2,
      publishTarget: "google",
      publishedAt: new Date(2026, 7, 1, 16, 0),
      publishedScheduleScope: "all",
      publishedDayRecords: publishedDayRecordsFor(
        publishedTasks,
        new Date(2026, 7, 1, 16, 0).toISOString(),
      ),
      now,
      taskInstances: [
        {
          id: 1,
          name: "Opening",
          date: "2026-08-01",
          optimised: optimisedSchedule,
          final: { ...optimisedSchedule, start_time: 630 },
          updated_at: new Date(2026, 7, 1, 16, 12).toISOString(),
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
      description:
        "Event changes pending - 1 day has changes since publishing today at 16:00.",
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

  it("shows publish failure timestamps when a publish attempt fails", () => {
    const now = new Date(2026, 7, 1, 16, 30);
    const summary = deriveEventStatusSummary({
      eventStatus: "draft",
      personCount: 2,
      locationCount: 1,
      publishTarget: "google",
      publishFailedAt: new Date(2026, 7, 1, 16, 20),
      now,
      taskInstances: [
        {
          id: 1,
          name: "Opening",
          date: "2026-08-01",
          optimised: optimisedSchedule,
          final: { ...optimisedSchedule },
        },
      ] as any,
      jobs: [],
    });

    expect(summary.primary).toMatchObject({
      title: "Event publishing failed",
      level: "blocked",
      description: "Publish failed today at 16:20.",
    });
  });

  it("prioritises conflicts over manual edits in the event-wide status", () => {
    const summary = deriveEventStatusSummary({
      eventStatus: "draft",
      personCount: 2,
      locationCount: 1,
      publishTarget: "google",
      people: [{ id: 10, first_name: "Anna", last_name: "Test" }],
      taskInstances: [
        {
          id: 1,
          name: "Opening",
          date: "2026-08-01",
          optimised: optimisedSchedule,
          final: { ...optimisedSchedule, end_time: 690 },
        },
        {
          id: 2,
          name: "Coffee",
          date: "2026-08-01",
          optimised: optimisedSchedule,
          final: { start_time: 630, end_time: 720, assigned_persons: [10] },
        },
      ] as any,
      jobs: [],
    });

    expect(summary.primary).toMatchObject({
      title: "Event action needed",
      level: "blocked",
      actionId: "conflicts",
    });
    expect(summary.items.find((item) => item.id === "conflicts")).toMatchObject(
      {
        status: "1 found",
        level: "blocked",
      },
    );
  });

  it("uses schedule fingerprints to clear changes pending after a successful publish", () => {
    const taskInstances = [
      {
        id: 1,
        name: "Opening",
        date: "2026-08-01",
        optimised: optimisedSchedule,
        final: { ...optimisedSchedule, start_time: 630 },
      },
    ] as any;
    const fingerprint = getScheduleFingerprint(taskInstances);

    const summary = deriveEventStatusSummary({
      eventStatus: "published",
      personCount: 2,
      locationCount: 1,
      publishTarget: "google",
      publishedScheduleScope: "all",
      publishedAt: new Date(2026, 7, 1, 16, 0),
      publishedDayRecords: publishedDayRecordsFor(
        taskInstances,
        new Date(2026, 7, 1, 16, 0).toISOString(),
      ),
      now: new Date(2026, 7, 1, 16, 30),
      taskInstances,
      currentScheduleFingerprint: fingerprint,
      publishedScheduleFingerprint: fingerprint,
      jobs: [],
    });

    expect(summary.primary).toMatchObject({
      title: "Event fully published",
      level: "ready",
    });
    expect(
      summary.items.find((item) => item.id === "publishing"),
    ).toMatchObject({
      status: "Fully published",
      level: "ready",
    });
  });

  it("does not mark the full event as published after a selected-day publish", () => {
    const taskInstances = [
      {
        id: 1,
        name: "Opening",
        date: "2026-08-01",
          optimised: optimisedSchedule,
          final: { ...optimisedSchedule },
      },
      {
        id: 2,
        name: "Coffee",
        date: "2026-08-02",
        optimised: optimisedSchedule,
        final: { ...optimisedSchedule },
      },
    ] as any;
    const selectedDayTasks = taskInstances.filter(
      (task: any) => task.date === "2026-08-01",
    );

    const summary = deriveEventStatusSummary({
      eventStatus: "published",
      personCount: 2,
      locationCount: 1,
      publishTarget: "google",
      taskInstances,
      publishedScheduleScope: "partial",
      publishedDayRecords: publishedDayRecordsFor(selectedDayTasks),
      publishedAt: new Date(2026, 7, 1, 16, 0),
      jobs: [],
    });

    expect(summary.primary).toMatchObject({
      title: "Event partially published",
      level: "review",
      actionId: "publishing",
    });
    expect(
      summary.items.find((item) => item.id === "publishing"),
    ).toMatchObject({
      status: "Partially published",
      level: "review",
    });
  });

  it("ignores unscheduled task instances when comparing published fingerprints", () => {
    const publishedTasks = [
      {
        id: 1,
        name: "Opening",
        date: "2026-08-01",
        optimised: optimisedSchedule,
        final: { ...optimisedSchedule, start_time: 630 },
      },
    ] as any;
    const currentTasks = [
      ...publishedTasks,
      {
        id: 2,
        name: "Draft task without schedule",
        date: "2026-08-01",
        optimised: {},
        final: {},
      },
    ] as any;

    expect(getScheduleFingerprint(currentTasks)).toBe(
      getScheduleFingerprint(publishedTasks),
    );

    const summary = deriveEventStatusSummary({
      eventStatus: "published",
      personCount: 2,
      locationCount: 1,
      publishTarget: "google",
      taskInstances: currentTasks,
      currentScheduleFingerprint: getScheduleFingerprint(currentTasks),
      publishedScheduleFingerprint: getScheduleFingerprint(publishedTasks),
      publishedScheduleScope: "all",
      publishedDayRecords: publishedDayRecordsFor(publishedTasks),
      jobs: [],
    });

    expect(
      summary.items.find((item) => item.id === "publishing"),
    ).toMatchObject({
      status: "Fully published",
      level: "ready",
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

describe("Calendar task confidence indicators", () => {
  it("renders subtle edited and conflict markers with details", () => {
    const consoleError = vi
      .spyOn(console, "error")
      .mockImplementation(() => {});

    render(
      <Calendar
        tasks={[
          {
            id: 1,
            name: "Opening",
            task_type_id: 1,
            task_type_name: "Session",
            task_type_color: "#2563eb",
            date: "2026-08-01",
            start_end_time: { start: "10:00", end: "11:00" },
            fields: {},
            field_definitions: [],
            assigned_persons: [10],
            resource_info: "Anna Test",
            manualChange: {
              summaries: ["Time changed"],
              details: [
                "Originally: 10:00-10:30 / Hall / Anna Test",
                "Now: 10:00-11:00 / Hall / Anna Test",
              ],
            },
            conflicts: {
              count: 1,
              messages: ["Anna Test is double-booked."],
              details: [
                "Opening overlaps with Coffee.",
                "Opening overlaps with Coffee.",
              ],
            },
          },
        ]}
        viewType="daily"
        selectedDate="2026-08-01"
        onTaskEdit={vi.fn()}
      />,
    );

    expect(screen.getByLabelText("Edited task")).toBeInTheDocument();
    expect(screen.getByLabelText("Task conflict")).toBeInTheDocument();
    expect(screen.getByLabelText("Task conflict")).toHaveClass("grid");
    expect(screen.getByLabelText("Task conflict").querySelector("svg")).toHaveClass(
      "block",
    );
    expect(screen.getByText("Edited after optimisation")).toBeInTheDocument();
    expect(screen.getByText("Anna Test is double-booked.")).toBeInTheDocument();
    expect(
      consoleError.mock.calls.some((call) =>
        String(call[0]).includes("same key"),
      ),
    ).toBe(false);

    consoleError.mockRestore();
  });

  it("renders flow-check issues with the same subtle corner marker style", () => {
    const { container } = render(
      <Calendar
        tasks={[
          {
            id: 2,
            name: "Bus Transfer",
            task_type_id: 1,
            task_type_name: "Transfer",
            task_type_color: "#2563eb",
            date: "2026-08-01",
            start_end_time: { start: "10:00", end: "10:30" },
            fields: {},
            field_definitions: [],
            assigned_persons: [10],
            resource_info: "Anna Test",
          },
        ]}
        viewType="daily"
        selectedDate="2026-08-01"
        onTaskEdit={vi.fn()}
        infeasibleTaskIds={new Set([2])}
        infeasibleTaskErrors={
          new Map([[2, ["Bus Transfer overlaps with Logic Workshop."]]])
        }
      />,
    );

    expect(screen.getByLabelText("Task check issue")).toBeInTheDocument();
    expect(screen.getByText("Flow check issue")).toBeInTheDocument();
    expect(
      screen.getByText("Bus Transfer overlaps with Logic Workshop."),
    ).toBeInTheDocument();
    expect(container.querySelector('[data-task-id="2"]')?.className).not.toContain(
      "ring-red-500",
    );
  });
});
