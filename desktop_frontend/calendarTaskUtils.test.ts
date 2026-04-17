/**
 * Tests for calendarTaskUtils — time conversion and task mapping.
 */
import { describe, it, expect } from "vitest";
import {
  minutesToTime,
  timeToMinutes,
  toCalendarTask,
  instancesToCalendarTasks,
} from "@/lib/calendarTaskUtils";

describe("minutesToTime", () => {
  it("converts 0 to 00:00", () => {
    expect(minutesToTime(0)).toBe("00:00");
  });

  it("converts 60 to 01:00", () => {
    expect(minutesToTime(60)).toBe("01:00");
  });

  it("converts 90 to 01:30", () => {
    expect(minutesToTime(90)).toBe("01:30");
  });

  it("converts 720 to 12:00 (noon)", () => {
    expect(minutesToTime(720)).toBe("12:00");
  });

  it("converts 1439 to 23:59 (end of day)", () => {
    expect(minutesToTime(1439)).toBe("23:59");
  });

  it("pads single-digit hours and minutes", () => {
    expect(minutesToTime(5)).toBe("00:05");
    expect(minutesToTime(65)).toBe("01:05");
  });
});

describe("timeToMinutes", () => {
  it("converts 00:00 to 0", () => {
    expect(timeToMinutes("00:00")).toBe(0);
  });

  it("converts 01:30 to 90", () => {
    expect(timeToMinutes("01:30")).toBe(90);
  });

  it("converts 12:00 to 720", () => {
    expect(timeToMinutes("12:00")).toBe(720);
  });

  it("converts 23:59 to 1439", () => {
    expect(timeToMinutes("23:59")).toBe(1439);
  });

  it("handles single-digit format", () => {
    expect(timeToMinutes("9:05")).toBe(545);
  });
});

describe("minutesToTime / timeToMinutes roundtrip", () => {
  it("roundtrips correctly for various values", () => {
    const values = [0, 30, 60, 90, 120, 480, 720, 1020, 1439];
    for (const mins of values) {
      expect(timeToMinutes(minutesToTime(mins))).toBe(mins);
    }
  });
});

describe("toCalendarTask", () => {
  const templates = [{ id: 10, name: "Workshop", fields: [] }] as any[];

  const taskTypes = [{ id: 1, name: "Session", color: "#ff0000" }] as any[];

  const persons = [
    { id: 100, first_name: "Alice", last_name: "Smith" },
    { id: 101, first_name: "Bob", last_name: "Jones" },
  ] as any[];

  const locations = [
    { id: 50, name: "Hall A" },
    { id: 51, name: "Hall B" },
  ] as any[];

  it("maps basic instance fields", () => {
    const instance = {
      id: 1,
      name: "Intro Workshop",
      task_type_id: 1,
      template_id: 10,
      date: "2026-08-01",
      final: {
        start_time: 540,
        end_time: 600,
        location: 50,
        assigned_persons: [100],
      },
      optimised: {},
    };

    const result = toCalendarTask(
      instance,
      templates,
      taskTypes,
      persons,
      locations,
    );
    expect(result.id).toBe(1);
    expect(result.name).toBe("Intro Workshop");
    expect(result.task_type_name).toBe("Session");
    expect(result.task_type_color).toBe("#ff0000");
    expect(result.location_name).toBe("Hall A");
    expect(result.resource_info).toBe("Alice Smith");
    expect(result.date).toBe("2026-08-01");
    expect(result.start_end_time).toEqual({ start: "09:00", end: "10:00" });
  });

  it("uses final schedule over optimised", () => {
    const instance = {
      id: 2,
      name: "Task",
      task_type_id: 1,
      template_id: 10,
      date: "2026-08-01",
      final: { start_time: 600, end_time: 660, assigned_persons: [] },
      optimised: { start_time: 480, end_time: 540, assigned_persons: [] },
    };

    const result = toCalendarTask(
      instance,
      templates,
      taskTypes,
      persons,
      locations,
    );
    expect(result.start_end_time).toEqual({ start: "10:00", end: "11:00" });
  });

  it("falls back to template name when instance has no name", () => {
    const instance = {
      id: 3,
      task_type_id: 1,
      template_id: 10,
      date: "2026-08-01",
      final: { assigned_persons: [] },
    };

    const result = toCalendarTask(
      instance,
      templates,
      taskTypes,
      persons,
      locations,
    );
    expect(result.name).toBe("Workshop");
  });

  it("joins multiple assigned persons", () => {
    const instance = {
      id: 4,
      name: "Team",
      task_type_id: 1,
      template_id: 10,
      date: "2026-08-01",
      final: { assigned_persons: [100, 101] },
    };

    const result = toCalendarTask(
      instance,
      templates,
      taskTypes,
      persons,
      locations,
    );
    expect(result.resource_info).toBe("Alice Smith, Bob Jones");
  });

  it("returns undefined start_end_time when times are missing", () => {
    const instance = {
      id: 5,
      name: "Flexible",
      task_type_id: 1,
      template_id: 10,
      date: "2026-08-01",
      final: { assigned_persons: [] },
    };

    const result = toCalendarTask(
      instance,
      templates,
      taskTypes,
      persons,
      locations,
    );
    expect(result.start_end_time).toBeUndefined();
  });

  it("handles unknown task type gracefully", () => {
    const instance = {
      id: 6,
      name: "Unknown",
      task_type_id: 999,
      template_id: 10,
      date: "2026-08-01",
      final: { assigned_persons: [] },
    };

    const result = toCalendarTask(
      instance,
      templates,
      taskTypes,
      persons,
      locations,
    );
    expect(result.task_type_name).toBe("");
    expect(result.task_type_color).toBe("#3b82f6"); // default blue
  });
});

describe("instancesToCalendarTasks", () => {
  const templates = [{ id: 10, name: "Task", fields: [] }] as any[];
  const taskTypes = [{ id: 1, name: "Type", color: "#000" }] as any[];
  const persons = [] as any[];
  const locations = [] as any[];

  it("filters by eventId and only includes optimised/final instances", () => {
    const instances = [
      {
        id: 1,
        event_id: 1,
        name: "A",
        task_type_id: 1,
        template_id: 10,
        date: "2026-08-01",
        final: { assigned_persons: [] },
      },
      {
        id: 2,
        event_id: 1,
        name: "B",
        task_type_id: 1,
        template_id: 10,
        date: "2026-08-01",
      }, // no final/optimised
      {
        id: 3,
        event_id: 2,
        name: "C",
        task_type_id: 1,
        template_id: 10,
        date: "2026-08-01",
        optimised: { assigned_persons: [] },
      }, // different event
    ];

    const result = instancesToCalendarTasks(
      instances,
      1,
      templates,
      taskTypes,
      persons,
      locations,
    );
    expect(result).toHaveLength(1);
    expect(result[0].name).toBe("A");
  });

  it("returns empty array when no matching instances", () => {
    const result = instancesToCalendarTasks(
      [],
      1,
      templates,
      taskTypes,
      persons,
      locations,
    );
    expect(result).toEqual([]);
  });
});
