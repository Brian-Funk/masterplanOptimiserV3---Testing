import React from "react";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import Calendar from "@/components/Calendar";
import { EventConfigSection } from "@/app/dashboard/settings/components/EventConfigSection";
import {
  DEFAULT_SCHEDULE_DAY_RANGE,
  normaliseScheduleDayRange,
} from "@/lib/scheduleDayRange";

const apiMocks = vi.hoisted(() => ({
  eventsApi: {
    getAll: vi.fn(),
    update: vi.fn(),
    updateCapabilities: vi.fn(),
  },
  capabilitiesApi: {
    getAll: vi.fn(),
  },
  personsApi: {
    getAll: vi.fn(),
  },
  taskTypesApi: {
    getAll: vi.fn(),
  },
}));

vi.mock("@/lib/api", () => apiMocks);

class FakeBroadcastChannel {
  static messages: unknown[] = [];

  onmessage: ((event: MessageEvent) => void) | null = null;

  constructor(public name: string) {}

  postMessage(message: unknown) {
    FakeBroadcastChannel.messages.push(message);
  }

  close() {}
}

const scheduledTask = {
  id: 1,
  name: "Late Session",
  task_type_id: 1,
  task_type_name: "Session",
  task_type_color: "#2563eb",
  date: "2026-08-01",
  start_end_time: { start: "13:00", end: "14:00" },
  fields: {},
  field_definitions: [],
};

describe("schedule day range", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    localStorage.clear();
    FakeBroadcastChannel.messages = [];
    vi.stubGlobal("BroadcastChannel", FakeBroadcastChannel);
    apiMocks.capabilitiesApi.getAll.mockResolvedValue([]);
    apiMocks.eventsApi.getAll.mockResolvedValue([]);
    apiMocks.personsApi.getAll.mockResolvedValue([]);
    apiMocks.taskTypesApi.getAll.mockResolvedValue([]);
    apiMocks.eventsApi.updateCapabilities.mockResolvedValue(undefined);
  });

  it("normalises invalid metadata to the current default range", () => {
    expect(normaliseScheduleDayRange(null)).toEqual(DEFAULT_SCHEDULE_DAY_RANGE);
    expect(normaliseScheduleDayRange({ startHour: 18, endHour: 18 })).toEqual(
      DEFAULT_SCHEDULE_DAY_RANGE,
    );
  });

  it("renders the configured visible schedule range", () => {
    render(
      <Calendar
        tasks={[]}
        viewType="daily"
        selectedDate="2026-08-01"
        onTaskEdit={vi.fn()}
        scheduleDayRange={{ startHour: 8, endHour: 11 }}
      />,
    );

    expect(screen.getByText("08:00")).toBeInTheDocument();
    expect(screen.getByText("10:00")).toBeInTheDocument();
    expect(screen.queryByText("06:00")).not.toBeInTheDocument();
    expect(screen.queryByText("11:00")).not.toBeInTheDocument();
  });

  it("resets Auto-Fit back to the configured event range", () => {
    render(
      <Calendar
        tasks={[scheduledTask]}
        viewType="daily"
        selectedDate="2026-08-01"
        onTaskEdit={vi.fn()}
        scheduleDayRange={{ startHour: 8, endHour: 11 }}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: "Auto-Fit" }));
    expect(screen.getByText("12:00 - 15:00")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Reset" }));
    expect(screen.queryByText("12:00 - 15:00")).not.toBeInTheDocument();
    expect(screen.getByText("08:00")).toBeInTheDocument();
  });

  it("opens task selection from the left time sidebar without affecting single click", () => {
    const onSlotDoubleClick = vi.fn();
    render(
      <Calendar
        tasks={[]}
        viewType="daily"
        selectedDate="2026-08-01"
        onTaskEdit={vi.fn()}
        onSlotDoubleClick={onSlotDoubleClick}
        scheduleDayRange={{ startHour: 8, endHour: 10 }}
      />,
    );

    fireEvent.click(screen.getByTestId("calendar-time-sidebar-slot-8-00"));
    expect(onSlotDoubleClick).not.toHaveBeenCalled();

    fireEvent.doubleClick(screen.getByTestId("calendar-time-sidebar-slot-8-00"));
    fireEvent.doubleClick(screen.getByTestId("calendar-time-sidebar-slot-8-30"));

    expect(onSlotDoubleClick).toHaveBeenNthCalledWith(1, {
      date: "2026-08-01",
      time: "08:00",
    });
    expect(onSlotDoubleClick).toHaveBeenNthCalledWith(2, {
      date: "2026-08-01",
      time: "08:30",
    });
  });

  it("saves the event display range while preserving day aliases", async () => {
    apiMocks.eventsApi.update.mockResolvedValue({
      id: 7,
      name: "Session",
      location: "Bern",
      start_date: "2026-08-01",
      end_date: "2026-08-01",
      meta_data: {},
    });

    render(
      <EventConfigSection
        selectedEvent={{
          id: 7,
          name: "Session",
          location: "Bern",
          start_date: "2026-08-01",
          end_date: "2026-08-01",
          meta_data: {
            day_aliases: { "2026-08-01": "Arrival Day" },
            schedule_day_range: { startHour: 6, endHour: 24 },
          },
        }}
        onEventUpdated={vi.fn()}
      />,
    );

    const selects = await screen.findAllByRole("combobox");
    fireEvent.change(selects[0], { target: { value: "9" } });
    fireEvent.change(selects[1], { target: { value: "18" } });
    fireEvent.click(screen.getByRole("button", { name: "Save Event Settings" }));

    await waitFor(() => expect(apiMocks.eventsApi.update).toHaveBeenCalled());
    expect(apiMocks.eventsApi.update).toHaveBeenCalledWith(
      7,
      expect.objectContaining({
        meta_data: expect.objectContaining({
          day_aliases: { "2026-08-01": "Arrival Day" },
          schedule_day_range: { startHour: 9, endHour: 18 },
        }),
      }),
    );
  });

  it("blocks invalid event display ranges", async () => {
    render(
      <EventConfigSection
        selectedEvent={{
          id: 8,
          name: "Session",
          location: "Bern",
          start_date: "2026-08-01",
          end_date: "2026-08-01",
          meta_data: { day_aliases: {} },
        }}
        onEventUpdated={vi.fn()}
      />,
    );

    const selects = await screen.findAllByRole("combobox");
    fireEvent.change(selects[0], { target: { value: "18" } });
    fireEvent.change(selects[1], { target: { value: "18" } });
    fireEvent.click(screen.getByRole("button", { name: "Save Event Settings" }));

    expect(
      screen.getByText("Schedule display range end time must be after start time."),
    ).toBeInTheDocument();
    expect(apiMocks.eventsApi.update).not.toHaveBeenCalled();
  });

});
