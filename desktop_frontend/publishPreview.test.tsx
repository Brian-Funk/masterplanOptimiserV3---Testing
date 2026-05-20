import React from "react";
import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { PublishPreviewModal } from "@/components/publish/PublishPreviewModal";
import {
  derivePublishPreview,
  getPublishTargetLabel,
  toPublishPreviewTarget,
} from "@/lib/publishPreview";
import type { DayPublishStatus } from "@/lib/eventStatusSummary";
import type { TaskInstance } from "@/lib/api";

function task(
  id: number,
  date: string,
  overrides: Partial<TaskInstance> = {},
): TaskInstance {
  return {
    id,
    name: `Task ${id}`,
    event_id: 1,
    date,
    is_floating: false,
    is_transfer: false,
    optimised: {
      start_time: 600,
      end_time: 660,
      location: 1,
      assigned_persons: [1],
    },
    final: {
      start_time: 600,
      end_time: 660,
      location: 1,
      assigned_persons: [1],
    },
    constraints: {},
    additional: {},
    ...overrides,
  };
}

function dayStatus(
  dayId: string,
  overrides: Partial<DayPublishStatus> = {},
): DayPublishStatus {
  return {
    dayId,
    label: dayId,
    fingerprint: `fingerprint-${dayId}`,
    isPublishable: true,
    isPublished: false,
    lastPublishedAt: null,
    hasChangesSincePublish: false,
    publishFailed: false,
    failureMessage: null,
    isOptimisedOrFinalised: true,
    conflictCount: 0,
    ...overrides,
  };
}

const dayLabels = {
  "2026-08-01": "Arrival Day",
  "2026-08-02": "Session Day",
  "2026-08-03": "Departure Day",
};

function labelDay(dayId: string) {
  return dayLabels[dayId as keyof typeof dayLabels] || dayId;
}

describe("publish preview derivation", () => {
  it("summarises selected-day publishing without implying the whole event is published", () => {
    const preview = derivePublishPreview({
      publishTarget: "google",
      scope: "selected_day",
      selectedDayId: "2026-08-01",
      dayStatuses: [dayStatus("2026-08-01"), dayStatus("2026-08-02")],
      taskInstances: [
        task(1, "2026-08-01", {
          final: {
            start_time: 630,
            end_time: 690,
            location: 1,
            assigned_persons: [1],
          },
        }),
        task(2, "2026-08-02"),
      ],
      allDayIds: ["2026-08-01", "2026-08-02"],
      getDayLabel: labelDay,
    });

    expect(preview.summary).toBe(
      "Arrival Day will be published to Google Calendar.",
    );
    expect(preview.scopeLabel).toBe("Arrival Day only");
    expect(preview.totalTasksToPublish).toBe(1);
    expect(preview.manualEditCount).toBe(1);
    expect(preview.explanation).toContain("Other days will remain unchanged");
    expect(preview.actionLabel).toBe("Publish Arrival Day");
  });

  it("shows which all-day publish days are ready and which days are skipped", () => {
    const preview = derivePublishPreview({
      publishTarget: "both",
      scope: "all_days",
      dayStatuses: [
        dayStatus("2026-08-01"),
        dayStatus("2026-08-02", {
          isPublishable: false,
          conflictCount: 2,
        }),
      ],
      taskInstances: [
        task(1, "2026-08-01"),
        task(2, "2026-08-02"),
      ],
      allDayIds: ["2026-08-01", "2026-08-02", "2026-08-03"],
      getDayLabel: labelDay,
    });

    expect(preview.targetLabel).toBe("Google Calendar and MP-Backend");
    expect(preview.totalDays).toBe(3);
    expect(preview.publishableDays).toBe(1);
    expect(preview.skippedDays).toBe(2);
    expect(preview.conflictCount).toBe(2);
    expect(preview.warnings).toContain("2 days will be skipped.");
    expect(preview.days.map((day) => day.status)).toEqual([
      "ready",
      "has_conflicts",
      "no_publishable_tasks",
    ]);
  });

  it("blocks publishing when no destination is configured", () => {
    const preview = derivePublishPreview({
      publishTarget: "none",
      scope: "selected_day",
      selectedDayId: "2026-08-01",
      dayStatuses: [dayStatus("2026-08-01")],
      taskInstances: [task(1, "2026-08-01")],
      getDayLabel: labelDay,
    });

    expect(preview.canPublish).toBe(false);
    expect(preview.summary).toBe("No publish target is configured.");
    expect(preview.blockingReasons).toContain(
      "No publish target is configured.",
    );
  });

  it("recognises already published days with human-readable timestamps", () => {
    const preview = derivePublishPreview({
      publishTarget: "mp-backend",
      scope: "selected_day",
      selectedDayId: "2026-08-01",
      dayStatuses: [
        dayStatus("2026-08-01", {
          isPublished: true,
          lastPublishedAt: "2026-08-01T16:00:00Z",
        }),
      ],
      taskInstances: [task(1, "2026-08-01")],
      getDayLabel: labelDay,
      now: new Date("2026-08-01T18:00:00Z"),
    });

    expect(preview.days[0].status).toBe("up_to_date");
    expect(preview.days[0].reason).toMatch(
      /^Last published today at \d{2}:00\.$/,
    );
  });

  it("maps publish target labels without exposing credentials", () => {
    expect(toPublishPreviewTarget("google")).toBe("google_calendar");
    expect(toPublishPreviewTarget("mp-backend")).toBe("mp_backend");
    expect(getPublishTargetLabel("both")).toBe("Google Calendar and MP-Backend");
    expect(getPublishTargetLabel(null)).toBe("No publish target");
  });
});

describe("PublishPreviewModal", () => {
  function readyPreview() {
    return derivePublishPreview({
      publishTarget: "both",
      scope: "all_days",
      dayStatuses: [dayStatus("2026-08-01"), dayStatus("2026-08-02")],
      taskInstances: [task(1, "2026-08-01"), task(2, "2026-08-02")],
      allDayIds: ["2026-08-01", "2026-08-02"],
      getDayLabel: labelDay,
    });
  }

  it("renders a calm summary, compact details, and the precise publish action", () => {
    render(
      <PublishPreviewModal
        open
        preview={readyPreview()}
        onCancel={() => {}}
        onConfirm={() => {}}
      />,
    );

    expect(screen.getByText("Preview publish")).toBeInTheDocument();
    expect(
      screen.getByText("2 days will be published to Google Calendar and MP-Backend."),
    ).toBeInTheDocument();
    expect(screen.getByText("Destination")).toBeInTheDocument();
    expect(screen.getByText("All 2 days")).toBeInTheDocument();
    expect(screen.getByText("Arrival Day")).toBeInTheDocument();
    expect(screen.getByText("Session Day")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Publish 2 days/ })).toBeEnabled();
  });

  it("disables confirmation when there is no publishable day", () => {
    const preview = derivePublishPreview({
      publishTarget: "google",
      scope: "selected_day",
      selectedDayId: "2026-08-03",
      dayStatuses: [],
      taskInstances: [],
      getDayLabel: labelDay,
    });

    render(
      <PublishPreviewModal
        open
        preview={preview}
        onCancel={() => {}}
        onConfirm={() => {}}
      />,
    );

    expect(screen.getByText("Cannot publish yet")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Publish/ })).toBeDisabled();
  });

  it("calls confirm and cancel handlers", async () => {
    const user = userEvent.setup();
    const onCancel = vi.fn();
    const onConfirm = vi.fn();

    render(
      <PublishPreviewModal
        open
        preview={readyPreview()}
        onCancel={onCancel}
        onConfirm={onConfirm}
      />,
    );

    await user.click(screen.getByRole("button", { name: /Publish 2 days/ }));
    await user.click(screen.getByRole("button", { name: "Cancel" }));

    expect(onConfirm).toHaveBeenCalledTimes(1);
    expect(onCancel).toHaveBeenCalledTimes(1);
  });

  it("hides day details without removing the main confirmation summary", async () => {
    const user = userEvent.setup();

    render(
      <PublishPreviewModal
        open
        preview={readyPreview()}
        onCancel={() => {}}
        onConfirm={() => {}}
      />,
    );

    await user.click(screen.getByRole("button", { name: "Hide details" }));

    expect(screen.queryByText("Arrival Day")).not.toBeInTheDocument();
    expect(screen.getByText("Preview publish")).toBeInTheDocument();
  });
});
