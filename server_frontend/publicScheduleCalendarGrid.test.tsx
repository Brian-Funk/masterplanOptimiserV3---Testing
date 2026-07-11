import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import React from "react";

import { PublicScheduleCalendarGrid } from "@/components/PublicScheduleCalendarGrid";

describe("PublicScheduleCalendarGrid", () => {
  it("renders timed public schedule items on the calendar timeline", () => {
    render(
      <PublicScheduleCalendarGrid
        selectedDate="2026-08-01"
        items={[
          {
            id: 1,
            title: "Opening Briefing",
            date: "2026-08-01",
            start_time: "09:00",
            end_time: "10:00",
            location_name: "Room A",
            audience_teams: [{ name: "Delegates", short_name: "DEL" }],
            description: "Bring laptops.",
            type_name: "Briefing",
            colour: "#7dd3fc",
            sort_order: 0,
          },
        ]}
      />,
    );

    expect(screen.getAllByText("Opening Briefing").length).toBeGreaterThan(0);
    expect(screen.getAllByText("09:00 - 10:00").length).toBeGreaterThan(0);
    expect(screen.getAllByText("DEL").length).toBeGreaterThan(0);
    expect(screen.getByText("Auto-Fit")).toBeInTheDocument();
  });
});
