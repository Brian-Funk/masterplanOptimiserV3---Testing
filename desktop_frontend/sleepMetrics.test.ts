/** Regression tests for sleep metrics on the desktop metrics board. */
import { describe, expect, it } from "vitest";

import { alignMetricLinePoints } from "@/lib/metrics/lineChartData";
import {
  MinimumSleepingHoursMetric,
  SleepingHoursMetric,
} from "@/lib/metrics/implementations/SleepHoursMetric";
import {
  LineChartVisualization,
  ScheduleData,
  TaskInstance,
} from "@/lib/metrics/MetricInterface";
import { buildMetricScheduleData } from "@/lib/metrics/metricScheduleData";

const people: ScheduleData["people"] = [
  {
    id: 1,
    name: "Alice Able",
    first_name: "Alice",
    last_name: "Able",
    email: "alice@example.test",
    capabilities: ["driver"],
  },
  {
    id: 2,
    name: "Bob Baker",
    first_name: "Bob",
    last_name: "Baker",
    email: "bob@example.test",
    capabilities: ["driver"],
  },
  {
    id: 3,
    name: "Clara Calm",
    first_name: "Clara",
    last_name: "Calm",
    email: "clara@example.test",
    capabilities: [],
  },
];

function task(
  id: string,
  personId: number,
  date: string,
  start: string,
  end: string,
  name: string,
): TaskInstance {
  return {
    id,
    person_ids: [personId],
    task_id: Number(id),
    task_type_id: 1,
    capability_ids: [],
    date,
    start_time: `${date}T${start}:00`,
    end_time: `${date}T${end}:00`,
    name,
  };
}

function sleepSchedule(): ScheduleData {
  return {
    people,
    capabilities: [
      {
        id: 10,
        name: "Driver",
        machine_name: "driver",
        color: "#2563eb",
      },
    ],
    taskTypes: [],
    dayAliases: {
      "2026-08-10": "Arrival Day",
      "2026-08-11": "Session Day 1",
      "2026-08-12": "Session Day 2",
    },
    eventDates: ["2026-08-10", "2026-08-11", "2026-08-12"],
    tasks: [
      task("1", 1, "2026-08-10", "20:00", "23:00", "Alice evening"),
      task("2", 2, "2026-08-10", "20:00", "22:00", "Bob evening"),
      task("3", 1, "2026-08-11", "07:00", "08:00", "Alice transfer"),
      task("4", 2, "2026-08-11", "06:00", "07:00", "Bob breakfast"),
      task("5", 1, "2026-08-11", "20:00", "21:00", "Alice night"),
      task("6", 2, "2026-08-11", "20:00", "23:00", "Bob night"),
      task("7", 1, "2026-08-12", "07:00", "08:00", "Alice morning"),
      task("8", 2, "2026-08-12", "06:00", "07:00", "Bob morning"),
    ],
  };
}

describe("sleeping-hours metric", () => {
  it("shows actual values for people and averages capability groups", async () => {
    const metric = new SleepingHoursMetric();
    const personResult = await metric.calculate(sleepSchedule(), undefined, {
      personIds: [1],
      capabilityIds: [],
      colorMap: {},
    });
    const personLine = (personResult.data as LineChartVisualization).lines[0];

    expect(personLine.label).toBe("Alice Able");
    expect(personLine.points).toEqual([
      { x: "2026-08-11", y: 8 },
      { x: "2026-08-12", y: 10 },
    ]);

    const groupResult = await metric.calculate(sleepSchedule(), undefined, {
      personIds: [],
      capabilityIds: [10],
      colorMap: {},
    });
    const groupLine = (groupResult.data as LineChartVisualization).lines[0];

    expect(groupLine.label).toBe("Driver (avg, 2p)");
    expect(groupLine.points).toEqual([
      { x: "2026-08-11", y: 8 },
      { x: "2026-08-12", y: 8.5 },
    ]);
    expect(groupResult.value).toBe(8.25);
    expect(groupResult.label).toBe("8.3 hrs avg sleep");
  });

  it("uses the least measurable sleep for capability groups", async () => {
    const result = await new MinimumSleepingHoursMetric().calculate(
      sleepSchedule(),
      undefined,
      { personIds: [], capabilityIds: [10], colorMap: {} },
    );
    const line = (result.data as LineChartVisualization).lines[0];

    expect(line.label).toBe("Driver (min, 2p)");
    expect(line.points).toEqual([
      { x: "2026-08-11", y: 8 },
      { x: "2026-08-12", y: 7 },
    ]);
    expect(result.value).toBe(7);
    expect(result.label).toBe("7.0 hrs minimum");
  });

  it("uses an assigned transfer as the first scheduled boundary", async () => {
    const apiPeople = [
      {
        id: 1,
        first_name: "Alice",
        last_name: "Able",
        email: "alice@example.test",
        global_data: { capabilities: [] },
      },
    ] as any[];
    const templates = [
      {
        id: 50,
        name: "Timed",
        fields: [{ id: "time", type: "start_end_time" }],
        custom_fields: [],
      },
    ] as any[];
    const { data } = buildMetricScheduleData(
      [
        {
          id: 1,
          event_id: 1,
          template_id: 50,
          task_type_id: 1,
          name: "Last task",
          date: "2026-08-10",
          is_transfer: false,
          final: {
            start_time: "20:00",
            end_time: "23:00",
            assigned_persons: [1],
          },
        },
        {
          id: 2,
          event_id: 1,
          template_id: 50,
          task_type_id: 1,
          name: "Morning transfer",
          date: "2026-08-11",
          is_transfer: true,
          final: {
            start_time: "06:00",
            end_time: "07:00",
            assigned_persons: [1],
          },
        },
      ] as any[],
      apiPeople,
      [],
      {},
      [],
      ["2026-08-10", "2026-08-11"],
      templates,
    );

    const result = await new SleepingHoursMetric().calculate(data, undefined, {
      personIds: [1],
      capabilityIds: [],
      colorMap: {},
    });

    expect(data.tasks.find((entry) => entry.id === "2")?.person_ids).toEqual([
      1,
    ]);
    expect((result.data as LineChartVisualization).lines[0].points).toEqual([
      { x: "2026-08-11", y: 7 },
    ]);
  });

  it("reports no value when no pair of schedule boundaries exists", async () => {
    const schedule = sleepSchedule();
    schedule.tasks = schedule.tasks.filter((entry) => entry.date === "2026-08-10");

    const result = await new SleepingHoursMetric().calculate(schedule);

    expect(result.value).toBe(0);
    expect(result.label).toBe("No sleep intervals");
  });
});

describe("sparse metric chart data", () => {
  it("renders explicitly missing sleep boundaries as gaps", () => {
    const line: LineChartVisualization["lines"][number] = {
      label: "Alice Able",
      points: [{ x: "2026-08-11", y: 8 }],
      missingPoints: ["2026-08-12"],
    };

    expect(
      alignMetricLinePoints(line, ["2026-08-11", "2026-08-12"]),
    ).toEqual([8, null]);
  });

  it("preserves zero-fill behaviour for existing metrics", () => {
    const line: LineChartVisualization["lines"][number] = {
      label: "Working hours",
      points: [{ x: "2026-08-11", y: 8 }],
    };

    expect(
      alignMetricLinePoints(line, ["2026-08-11", "2026-08-12"]),
    ).toEqual([8, 0]);
  });
});
