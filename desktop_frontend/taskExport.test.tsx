import React from "react";
import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { TaskInstance } from "@/lib/api";
import {
  buildTaskExportPayload,
  buildTaskExportPayloads,
} from "@/lib/taskExport";
import { ExportSelectedTasksModal } from "@/app/dashboard/admin/tabs/cmi/ExportSelectedTasksModal";

function task(overrides: Partial<TaskInstance> = {}): TaskInstance {
  return {
    id: 101,
    name: "Opening Briefing",
    event_id: 4,
    template_id: 12,
    task_type_id: 6,
    date: "2026-08-10",
    day_index: 0,
    is_floating: false,
    is_transfer: true,
    field_values: {
      time: { start: "09:00", end: "10:00" },
      location: 3,
      people: [{ type: "person", id: 9 }],
    },
    constraints: { locked: true },
    additional: {
      notes: "Bring printed agenda.",
      google_calendar_event_id: "secret-generated-id",
      manual_edit_state: "edited",
    },
    optimised: { assigned_persons: [9] },
    final: { assigned_persons: [9] },
    created_at: "2026-05-01T10:00:00Z",
    updated_at: "2026-05-02T10:00:00Z",
    ...overrides,
  };
}

describe("task export payload helper", () => {
  it("copies one task to a target day while dropping generated state", () => {
    const source = task();
    const payload = buildTaskExportPayload(
      source,
      "2026-08-10",
      "2026-08-12",
      "2026-08-10",
    );

    expect(payload).toMatchObject({
      event_id: 4,
      template_id: 12,
      name: "Opening Briefing",
      task_type_id: 6,
      date: "2026-08-12",
      day_index: 2,
      is_floating: false,
      is_transfer: true,
      field_values: source.field_values,
      constraints: source.constraints,
      additional: { notes: "Bring printed agenda." },
    });
    expect(payload).not.toHaveProperty("id");
    expect(payload).not.toHaveProperty("optimised");
    expect(payload).not.toHaveProperty("final");
    expect(payload).not.toHaveProperty("created_at");
    expect(payload.field_values).not.toBe(source.field_values);
    expect(payload.constraints).not.toBe(source.constraints);
    expect(source.additional).toHaveProperty("google_calendar_event_id");
  });

  it("creates one payload per selected task and target day", () => {
    const payloads = buildTaskExportPayloads(
      [task({ id: 1, name: "A" }), task({ id: 2, name: "B" })],
      "2026-08-10",
      ["2026-08-11", "2026-08-12"],
      "2026-08-10",
    );

    expect(payloads).toHaveLength(4);
    expect(payloads.map((payload) => payload.name)).toEqual([
      "A",
      "B",
      "A",
      "B",
    ]);
    expect(payloads.map((payload) => payload.date)).toEqual([
      "2026-08-11",
      "2026-08-11",
      "2026-08-12",
      "2026-08-12",
    ]);
  });

  it("preserves overnight actual-date offset for next-day tasks", () => {
    const source = task({
      date: "2026-08-11",
      field_values: { time: { start: "01:00", end: "02:00" } },
    });

    const payload = buildTaskExportPayload(
      source,
      "2026-08-10",
      "2026-08-12",
      "2026-08-10",
    );

    expect(payload.date).toBe("2026-08-13");
    expect(payload.day_index).toBe(2);
  });
});

describe("ExportSelectedTasksModal", () => {
  const modalProps = {
    open: true,
    selectedTasks: [
      task({ id: 1, name: "Opening Briefing" }),
      task({ id: 2, name: "Jury Meeting" }),
      task({ id: 3, name: "Coffee Break Support" }),
      task({ id: 4, name: "Room Setup" }),
      task({ id: 5, name: "Evening Debrief" }),
    ],
    sourceDate: "2026-08-10",
    eventStartDate: "2026-08-10",
    eventEndDate: "2026-08-12",
    dayAliases: {
      "2026-08-10": "Arrival Day",
      "2026-08-11": "Session Day 1",
      "2026-08-12": "Session Day 2",
    },
    onCancel: vi.fn(),
    onExport: vi.fn(),
  };

  it("renders the selected task summary and excludes the source day", () => {
    render(<ExportSelectedTasksModal {...modalProps} />);

    expect(screen.getByText("Export selected tasks")).toBeInTheDocument();
    expect(screen.getByText(/From Arrival Day/)).toBeInTheDocument();
    expect(screen.getByText("5 selected tasks")).toBeInTheDocument();
    expect(screen.getByText("Opening Briefing")).toBeInTheDocument();
    expect(screen.getByText("+ 1 more")).toBeInTheDocument();
    expect(screen.queryByLabelText(/Arrival Day/)).not.toBeInTheDocument();
    expect(screen.getByLabelText(/Session Day 1/)).toBeInTheDocument();
    expect(screen.getByLabelText(/Session Day 2/)).toBeInTheDocument();
  });

  it("disables export until a target day is selected", async () => {
    const user = userEvent.setup();
    const onExport = vi.fn();
    render(<ExportSelectedTasksModal {...modalProps} onExport={onExport} />);

    expect(screen.getByRole("button", { name: "Export tasks" })).toBeDisabled();

    await user.click(screen.getByLabelText(/Session Day 1/));

    expect(screen.getByText(/5 tasks will be copied to 1 day/)).toBeInTheDocument();
    expect(screen.getByText(/5 new tasks will be created/)).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Export tasks" }));

    expect(onExport).toHaveBeenCalledWith(["2026-08-11"]);
  });

  it("shows an empty state when there are no other days", () => {
    render(
      <ExportSelectedTasksModal
        {...modalProps}
        eventEndDate="2026-08-10"
      />,
    );

    expect(screen.getByText("There are no other days in this event.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Export tasks" })).toBeDisabled();
  });

  it("blocks export while a previous export is running", () => {
    render(<ExportSelectedTasksModal {...modalProps} isExporting />);

    expect(screen.getByRole("button", { name: "Exporting..." })).toBeDisabled();
  });
});
