import React from "react";
import { describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";
import Calendar, { type CalendarTask } from "@/components/Calendar";
import CalendarViewSlide from "@/components/presentation/CalendarViewSlide";
import PresentSidebar from "@/components/presentation/PresentSidebar";
import PresentSlide from "@/components/presentation/PresentSlide";

vi.mock("@/contexts/ShortcutContext", () => ({
  useShortcuts: () => ({
    getShortcutBinding: (id: string) =>
      ({
        "presentation.toggleTaskList": "S",
        "presentation.previousTask": "ArrowLeft",
        "presentation.nextTask": "ArrowRight",
        "presentation.previousDay": "ArrowUp",
        "presentation.nextDay": "ArrowDown",
        "presentation.toggleView": "C",
        "presentation.toggleCalendarSidebar": "R",
        "presentation.toggleFullscreen": "F",
        "presentation.backOrClose": "Escape",
      })[id] || "Unassigned",
  }),
}));

const tasks: CalendarTask[] = [
  {
    id: 1,
    name: "Opening Briefing",
    task_type_id: 1,
    task_type_name: "Session",
    task_type_color: "#2563eb",
    location_id: 2,
    location_name: "Main Hall",
    date: "2026-08-01",
    start_end_time: { start: "09:00", end: "10:00" },
    fields: {},
    field_definitions: [],
    assigned_persons: [10],
    resource_info: "Anna Keller",
    manualChange: {
      summaries: ["Time changed"],
      details: ["Originally: 09:30 - 10:30"],
    },
  },
  {
    id: 2,
    name: "Workshop Setup",
    task_type_id: 1,
    task_type_name: "Session",
    task_type_color: "#16a34a",
    location_id: 3,
    location_name: "Room A",
    date: "2026-08-01",
    start_end_time: { start: "10:30", end: "11:30" },
    fields: {},
    field_definitions: [],
    assigned_persons: [11],
    resource_info: "Ben Meyer",
    conflicts: {
      count: 1,
      messages: ["Ben Meyer is double-booked."],
      details: ["Workshop Setup overlaps with Logistics."],
    },
  },
];

describe("presentation mode polish", () => {
  it("renders the calendar in presentation mode without the editing toolbar", () => {
    render(
      <Calendar
        tasks={tasks}
        viewType="daily"
        selectedDate="2026-08-01"
        onTaskEdit={() => {}}
        presentationMode
        density="comfortable"
      />,
    );

    expect(screen.queryByRole("button", { name: "Auto-Fit" })).toBeNull();
    const calendar = document.querySelector("[data-presentation-mode='true']");
    expect(calendar).toHaveAttribute("data-calendar-density", "comfortable");
    expect(screen.getByText("Opening Briefing")).toBeInTheDocument();
    expect(screen.getAllByText("09:00 - 10:00").length).toBeGreaterThan(0);
    expect(screen.getByLabelText("Edited task")).toBeInTheDocument();
    expect(screen.getByLabelText("Task conflict")).toBeInTheDocument();
  });

  it("passes compact density through the presentation calendar slide", () => {
    render(
      <CalendarViewSlide
        date="2026-08-01"
        dayLabel="Arrival Day"
        tasks={tasks}
        density="compact"
      />,
    );

    expect(
      screen.getByTestId("presentation-calendar-view"),
    ).toBeInTheDocument();
    expect(document.querySelector("[data-calendar-density='compact']")).not.toBe(
      null,
    );
  });

  it("shows readable task detail hierarchy for presentation slides", () => {
    render(
      <PresentSlide
        task={{
          ...tasks[0],
          field_definitions: [{ id: "notes", name: "Notes", type: "text" }],
          fields: { notes: "Coordinate with the hosts before the doors open." },
        }}
        slideIndex={0}
        totalSlides={2}
        persons={[{ id: 10, first_name: "Anna", last_name: "Keller" } as any]}
        onBack={() => {}}
      />,
    );

    expect(screen.getByTestId("presentation-detail-slide")).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Opening Briefing" })).toBeInTheDocument();
    expect(screen.getByText("09:00 - 10:00")).toBeInTheDocument();
    expect(screen.getByText("Main Hall")).toBeInTheDocument();
    expect(screen.getByText("Anna Keller")).toBeInTheDocument();
    expect(screen.getByText("Coordinate with the hosts before the doors open.")).toBeInTheDocument();
  });

  it("keeps the presentation task sidebar compact and task-focused", () => {
    const onSelectTask = vi.fn();
    render(
      <PresentSidebar
        dayGroups={[
          {
            date: "2026-08-01",
            label: "Arrival Day - 01.08.2026",
            tasks,
          },
        ]}
        currentTaskId={1}
        collapsed={false}
        onToggle={() => {}}
        onSelectTask={onSelectTask}
      />,
    );

    expect(screen.getByTestId("presentation-task-sidebar")).toBeInTheDocument();
    expect(screen.getByText("Arrival Day - 01.08.2026")).toBeInTheDocument();
    fireEvent.click(screen.getByText("Workshop Setup"));
    expect(onSelectTask).toHaveBeenCalledWith(2);
  });

  it("keeps shortcut help available without showing it by default", () => {
    render(
      <PresentSidebar
        dayGroups={[{ date: "2026-08-01", label: "Arrival Day", tasks }]}
        currentTaskId={null}
        collapsed={false}
        onToggle={() => {}}
        onSelectTask={() => {}}
      />,
    );

    expect(screen.queryByText("Keyboard shortcuts")).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Keyboard shortcuts" }));
    expect(screen.getByText("Keyboard shortcuts")).toBeInTheDocument();
    expect(screen.getByText("Previous / next task")).toBeInTheDocument();
    expect(screen.getByText("ArrowLeft / ArrowRight")).toBeInTheDocument();
  });
});
