import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import React from "react";

import { CalendarGrid } from "@/components/CalendarGrid";
import { TaskDetailModal, type Task } from "@/components/TaskDetailModal";

const editedTask: Task = {
  id: 1,
  external_task_id: 101,
  name: "Opening Briefing",
  summary: null,
  description: null,
  start: "2026-05-21T09:00:00",
  end: "2026-05-21T10:00:00",
  location_name: "Room A",
  location_address: null,
  task_type_code: "session",
  task_type_name: "Session",
  color: "#4A90D9",
  attendees: [],
  field_assignments: null,
  field_values: null,
  field_definitions: null,
  additional: null,
  sort_order: 0,
  has_web_edit: true,
  web_edit_edited_at: "2026-05-21T14:20:00",
  web_edit_edited_by: "Anna",
  web_edit_edited_by_user_id: 7,
  web_edit_change_summary: ["Time changed"],
};

describe("web edit task markers", () => {
  it("uses the desktop-style pencil indicator on calendar tasks", () => {
    render(
      <CalendarGrid
        tasks={[editedTask]}
        selectedDate="2026-05-21"
        highlightedPersonId={null}
        highlightMode="off"
        onTaskDoubleClick={vi.fn()}
      />,
    );

    const marker = screen.getByLabelText(
      /Edited on the web by Anna .* at 14:20\. Time changed\./,
    );
    expect(marker.className).toContain("rounded-full");
    expect(marker.className).toContain("bg-amber-500/10");
    expect(marker.querySelector("svg")).not.toBeNull();
  });

  it("uses the same pencil indicator in the task detail modal", () => {
    render(
      <TaskDetailModal
        task={editedTask}
        canEdit
        eventId={1}
        persons={[]}
        onClose={vi.fn()}
        onDataChanged={vi.fn()}
        onDraftEdit={vi.fn()}
        onDraftDelete={vi.fn()}
      />,
    );

    const markers = screen.getAllByLabelText(
      /Edited on the web by Anna .* at 14:20\. Time changed\./,
    );
    expect(markers[0].className).toContain("rounded-full");
    expect(markers[0].querySelector("svg")).not.toBeNull();
    expect(screen.getByText("Edited on the web")).toBeInTheDocument();
  });
});
