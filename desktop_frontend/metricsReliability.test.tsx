import React from "react";
import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";

import MetricResourceSelector from "@/components/metrics/MetricResourceSelector";
import {
  buildMetricScheduleData,
  calculatePersonHoursByDay,
  dedupeMetricIds,
  findMaxHoursViolations,
  findMaxHoursViolationBreakdowns,
} from "@/lib/metrics/metricScheduleData";
import { MetricRegistry } from "@/lib/metrics/MetricRegistry";
import { CFIIMetric } from "@/lib/metrics/implementations/CFIIMetric";
import { FairnessMetric } from "@/lib/metrics/implementations/FairnessMetric";
import { FatigueTimelineMetric } from "@/lib/metrics/implementations/FatigueTimelineMetric";
import { MaxWorkStreakMetric } from "@/lib/metrics/implementations/MaxWorkStreakMetric";
import {
  TaskTypeCountSpiderMetric,
  TaskTypeHoursSpiderMetric,
} from "@/lib/metrics/implementations/TaskTypeSpiderMetric";
import {
  AbsoluteWorkingHoursMetric,
  AverageWorkingHoursMetric,
  MaxWorkingHoursMetric,
} from "@/lib/metrics/implementations/TotalHoursMetric";
import { WorkloadSpiderMetric } from "@/lib/metrics/implementations/WorkloadSpiderMetric";

const people = [
  {
    id: 1,
    first_name: "Alice",
    last_name: "Able",
    email: "alice@example.test",
    max_hours_per_day: 2.5,
    capabilities: ["driver"],
  },
  {
    id: 2,
    first_name: "Bob",
    last_name: "Baker",
    email: "bob@example.test",
    capabilities: ["driver"],
  },
  {
    id: 3,
    first_name: "Clara",
    last_name: "Calm",
    email: "clara@example.test",
    capabilities: [],
  },
] as any[];

const capabilities = [
  { id: 10, name: "Driver", machine_name: "driver" },
  { id: 20, name: "Medic", machine_name: "medic" },
] as any[];

const taskTypes = [
  { id: 100, name: "Shift", color: "#333", fatigue_score: 1 },
  { id: 200, name: "Transport", color: "#666", fatigue_score: 2 },
] as any[];

const templates = [
  {
    id: 500,
    name: "Normal Task",
    fields: [
      { id: "time", type: "start_end_time" },
      { id: "people", type: "persons_list" },
      { id: "caps", type: "capabilities_list" },
    ],
    custom_fields: [],
  },
] as any[];

function buildWorkloadSchedule() {
  return buildMetricScheduleData(
    [
      {
        id: 1,
        name: "Alice two hours",
        event_id: 1,
        template_id: 500,
        task_type_id: 100,
        date: "2026-08-10",
        is_floating: false,
        is_transfer: false,
        final: { start_time: "10:00", end_time: "12:00", assigned_persons: [1] },
      },
      {
        id: 2,
        name: "Alice one hour",
        event_id: 1,
        template_id: 500,
        task_type_id: 100,
        date: "2026-08-10",
        is_floating: false,
        is_transfer: false,
        final: { start_time: "13:00", end_time: "14:00", assigned_persons: [1] },
      },
      {
        id: 3,
        name: "Bob one hour",
        event_id: 1,
        template_id: 500,
        task_type_id: 100,
        date: "2026-08-10",
        is_floating: false,
        is_transfer: false,
        final: { start_time: "10:00", end_time: "11:00", assigned_persons: [2] },
      },
      {
        id: 4,
        name: "Two person task",
        event_id: 1,
        template_id: 500,
        task_type_id: 100,
        date: "2026-08-10",
        is_floating: false,
        is_transfer: false,
        final: { start_time: "15:00", end_time: "16:00", assigned_persons: [1, 2] },
      },
      {
        id: 5,
        name: "Unassigned task",
        event_id: 1,
        template_id: 500,
        task_type_id: 100,
        date: "2026-08-10",
        is_floating: false,
        is_transfer: false,
        final: { start_time: "17:00", end_time: "18:00", assigned_persons: [] },
      },
    ] as any[],
    people,
    capabilities,
    {},
    taskTypes,
    ["2026-08-10"],
    templates,
  ).data;
}
describe("metrics schedule data extraction", () => {
  it("deduplicates selected metric ids", () => {
    expect(dedupeMetricIds([2, 2, 1, Number.NaN, 0, 1])).toEqual([2, 1]);
  });

  it("prefers final assignments over optimised assignments and includes field assignments", () => {
    const { data } = buildMetricScheduleData(
      [
        {
          id: 1,
          name: "Final task",
          event_id: 1,
          template_id: 500,
          task_type_id: 100,
          date: "2026-08-10",
          is_floating: false,
          is_transfer: false,
          optimised: { start_time: "09:00", end_time: "10:00", assigned_persons: [3] },
          final: {
            start_time: "09:00",
            end_time: "10:00",
            assigned_persons: [1],
            field_assignments: { people: [2, 2] },
          },
        },
      ] as any[],
      people,
      capabilities,
      {},
      taskTypes,
      ["2026-08-10"],
      templates,
    );

    expect(data.tasks[0].person_ids).toEqual([1, 2]);
  });

  it("uses optimised assignments when final is absent", () => {
    const { data } = buildMetricScheduleData(
      [
        {
          id: 1,
          name: "Optimised task",
          event_id: 1,
          template_id: 500,
          task_type_id: 100,
          date: "2026-08-10",
          is_floating: false,
          is_transfer: false,
          optimised: { start_time: "09:00", end_time: "10:00", assigned_persons: [2] },
        },
      ] as any[],
      people,
      capabilities,
      {},
      taskTypes,
      ["2026-08-10"],
      templates,
    );

    expect(data.tasks[0].person_ids).toEqual([2]);
  });

  it("only treats typed persons_list fields as raw people and never capabilities_list values", () => {
    const { data } = buildMetricScheduleData(
      [
        {
          id: 1,
          name: "Raw task",
          event_id: 1,
          template_id: 500,
          task_type_id: 100,
          date: "2026-08-10",
          is_floating: false,
          is_transfer: false,
          field_values: {
            time: { start: "10:00", end: "11:00" },
            people: [1, { type: "person", id: 2 }, { type: "group", id: 9 }],
            caps: [{ id: 10, quantity: 1 }],
            location: [3],
          },
        },
      ] as any[],
      people,
      capabilities,
      {},
      taskTypes,
      ["2026-08-10"],
      templates,
    );

    expect(data.tasks[0].person_ids).toEqual([1, 2]);
    expect(data.tasks[0].capability_ids).toEqual([10]);
  });

  it("handles 24:00 and cross-midnight times without negative duration", () => {
    const { data } = buildMetricScheduleData(
      [
        {
          id: 1,
          name: "Late task",
          event_id: 1,
          template_id: 500,
          task_type_id: 100,
          date: "2026-08-10",
          is_floating: false,
          is_transfer: false,
          final: { start_time: "23:00", end_time: "24:00", assigned_persons: [1] },
        },
        {
          id: 2,
          name: "Overnight task",
          event_id: 1,
          template_id: 500,
          task_type_id: 100,
          date: "2026-08-10",
          is_floating: false,
          is_transfer: false,
          final: { start_time: "23:30", end_time: "01:00", assigned_persons: [1] },
        },
      ] as any[],
      people,
      capabilities,
      {},
      taskTypes,
      ["2026-08-10"],
      templates,
    );

    expect(data.tasks.map((task) => task.end_time)).toEqual([
      "2026-08-11T00:00:00",
      "2026-08-11T01:00:00",
    ]);
  });
});


describe("metrics working-day grouping", () => {
  it("groups after-midnight work into the previous working day when the event range crosses midnight", () => {
    const { data } = buildMetricScheduleData(
      [
        {
          id: 1,
          name: "Overnight support",
          event_id: 1,
          template_id: 500,
          task_type_id: 100,
          date: "2026-08-11",
          is_floating: false,
          is_transfer: false,
          final: { start_time: "01:00", end_time: "02:00", assigned_persons: [1] },
        },
      ] as any[],
      people,
      capabilities,
      {},
      taskTypes,
      ["2026-08-10", "2026-08-11"],
      templates,
      { 1: { offsetHour: 4 } },
    );

    expect(data.tasks[0].date).toBe("2026-08-10");
  });
});

describe("working-hours metrics", () => {
  const { data: schedule } = buildMetricScheduleData(
    [
      {
        id: 1,
        name: "Alice two hours",
        event_id: 1,
        template_id: 500,
        task_type_id: 100,
        date: "2026-08-10",
        is_floating: false,
        is_transfer: false,
        final: { start_time: "10:00", end_time: "12:00", assigned_persons: [1] },
      },
      {
        id: 2,
        name: "Alice one hour",
        event_id: 1,
        template_id: 500,
        task_type_id: 100,
        date: "2026-08-10",
        is_floating: false,
        is_transfer: false,
        final: { start_time: "13:00", end_time: "14:00", assigned_persons: [1] },
      },
      {
        id: 3,
        name: "Bob one hour",
        event_id: 1,
        template_id: 500,
        task_type_id: 100,
        date: "2026-08-10",
        is_floating: false,
        is_transfer: false,
        final: { start_time: "10:00", end_time: "11:00", assigned_persons: [2] },
      },
      {
        id: 4,
        name: "Two person task",
        event_id: 1,
        template_id: 500,
        task_type_id: 100,
        date: "2026-08-10",
        is_floating: false,
        is_transfer: false,
        final: { start_time: "15:00", end_time: "16:00", assigned_persons: [1, 2] },
      },
      {
        id: 5,
        name: "Unassigned task",
        event_id: 1,
        template_id: 500,
        task_type_id: 100,
        date: "2026-08-10",
        is_floating: false,
        is_transfer: false,
        final: { start_time: "17:00", end_time: "18:00", assigned_persons: [] },
      },
    ] as any[],
    people,
    capabilities,
    {},
    taskTypes,
    ["2026-08-10"],
    templates,
  );

  it("counts unassigned tasks as zero person-hours and multi-person tasks as duration times people", async () => {
    const metric = new AbsoluteWorkingHoursMetric();
    const result = await metric.calculate(schedule);

    expect(result.value).toBe(6);
    expect(result.label).toContain("6.0 hours total");
  });

  it("keeps zero-hour people in average denominator and reports max-hour violations", async () => {
    const metric = new AverageWorkingHoursMetric();
    const result = await metric.calculate(schedule);

    expect(result.value).toBe(2);
    expect(result.label).toContain("2.0 avg hrs/person");
    expect(result.label).toContain("over limit");
    expect(findMaxHoursViolations(schedule)).toMatchObject([
      { personId: 1, hours: 4, maxHours: 2.5 },
    ]);
  });
});


describe("CFII heatmap ordering", () => {
  it("keeps event-date order while displaying day aliases", async () => {
    const { data } = buildMetricScheduleData(
      [
        {
          id: 1,
          name: "Day one",
          event_id: 1,
          template_id: 500,
          task_type_id: 100,
          date: "2026-08-10",
          is_floating: false,
          is_transfer: false,
          final: { start_time: "10:00", end_time: "11:00", assigned_persons: [1] },
        },
        {
          id: 2,
          name: "Day two",
          event_id: 1,
          template_id: 500,
          task_type_id: 100,
          date: "2026-08-11",
          is_floating: false,
          is_transfer: false,
          final: { start_time: "10:00", end_time: "11:00", assigned_persons: [2] },
        },
      ] as any[],
      people,
      capabilities,
      {
        "2026-08-10": "Session Day 2",
        "2026-08-11": "Arrival Day",
      },
      taskTypes,
      ["2026-08-10", "2026-08-11"],
      templates,
    );

    const result = await new CFIIMetric().calculate(data);
    const heatmap = result.data as any;

    expect(heatmap.xOrder).toEqual(["2026-08-10", "2026-08-11"]);
    expect(heatmap.xLabels).toEqual({
      "2026-08-10": "Session Day 2",
      "2026-08-11": "Arrival Day",
    });
    expect(Array.from(new Set(heatmap.data.map((point: any) => point.x)))).toEqual([
      "2026-08-10",
      "2026-08-11",
    ]);
  });
});

describe("max working-hours metric", () => {
  it("shows selected person actual hours with a dashed configured limit", async () => {
    const metric = new MaxWorkingHoursMetric();
    const result = await metric.calculate(buildWorkloadSchedule(), undefined, {
      personIds: [1],
      capabilityIds: [],
      colorMap: {},
    });
    const lines = (result.data as any).lines;

    expect(lines[0]).toMatchObject({ label: "Alice Able" });
    expect(lines[0].points).toEqual([{ x: "2026-08-10", y: 4 }]);
    expect(lines[1]).toMatchObject({ label: "Alice Able limit", style: "dashed" });
    expect(lines[1].points).toEqual([{ x: "2026-08-10", y: 2.5 }]);
    expect(result.label).toContain("Alice Able 4h");
    expect(result.label).toContain("limit 2.5h");
  });

  it("uses the maximum scheduled member for capability filters", async () => {
    const metric = new MaxWorkingHoursMetric();
    const result = await metric.calculate(buildWorkloadSchedule(), undefined, {
      personIds: [],
      capabilityIds: [10],
      colorMap: {},
    });
    const lines = (result.data as any).lines;

    expect(lines[0]).toMatchObject({ label: "Driver max" });
    expect(lines[0].points).toEqual([{ x: "2026-08-10", y: 4 }]);
    expect(lines[1]).toMatchObject({ label: "Driver limit", style: "dashed" });
  });

  it("identifies the daily event max without selected filters", async () => {
    const metric = new MaxWorkingHoursMetric();
    const result = await metric.calculate(buildWorkloadSchedule(), undefined, {
      personIds: [],
      capabilityIds: [],
      colorMap: {},
    });
    const lines = (result.data as any).lines;

    expect(lines[0]).toMatchObject({ label: "Daily max" });
    expect(lines[0].points).toEqual([{ x: "2026-08-10", y: 4 }]);
    expect(lines[1]).toMatchObject({ label: "Limit for daily max", style: "dashed" });
  });
});


describe("metric registry coverage", () => {
  it("registers every metrics-board metric and each metric calculates against a deterministic schedule", async () => {
    const registry = MetricRegistry.getInstance();

    expect(registry.listMetrics()).toEqual([
      "average_working_hours",
      "absolute_working_hours",
      "max_working_hours",
      "minimum_sleeping_hours",
      "sleeping_hours",
      "workload_spider",
      "fairness",
      "task_type_count_spider",
      "task_type_hours_spider",
      "fatigue_timeline",
      "max_work_streak",
      "cfii",
    ]);

    for (const metric of registry.getAll()) {
      const result = await metric.calculate(buildWorkloadSchedule(), undefined, {
        personIds: [],
        capabilityIds: [],
        colorMap: {},
      });
      expect(Number.isFinite(result.value)).toBe(true);
      expect(result.label).toBeTruthy();
      expect(result.data).toBeTruthy();
    }
  });
});

describe("working-hours metric line semantics", () => {
  it("keeps zero-work event days visible for selected people", async () => {
    const { data } = buildMetricScheduleData(
      [
        {
          id: 1,
          name: "Alice one hour",
          event_id: 1,
          template_id: 500,
          task_type_id: 100,
          date: "2026-08-10",
          is_floating: false,
          is_transfer: false,
          final: { start_time: "10:00", end_time: "11:00", assigned_persons: [1] },
        },
      ] as any[],
      people,
      capabilities,
      {},
      taskTypes,
      ["2026-08-10", "2026-08-11"],
      templates,
    );

    const result = await new AverageWorkingHoursMetric().calculate(data, undefined, {
      personIds: [1],
      capabilityIds: [],
      colorMap: {},
    });

    expect((result.data as any).lines[0].points).toEqual([
      { x: "2026-08-10", y: 1 },
      { x: "2026-08-11", y: 0 },
    ]);
  });

  it("uses raw person-hours for absolute capability lines and averages for average capability lines", async () => {
    const schedule = buildWorkloadSchedule();

    const absolute = await new AbsoluteWorkingHoursMetric().calculate(schedule, undefined, {
      personIds: [],
      capabilityIds: [10],
      colorMap: {},
    });
    expect((absolute.data as any).lines[0]).toMatchObject({ label: "Driver (total)" });
    expect((absolute.data as any).lines[0].points).toEqual([{ x: "2026-08-10", y: 6 }]);

    const average = await new AverageWorkingHoursMetric().calculate(schedule, undefined, {
      personIds: [],
      capabilityIds: [10],
      colorMap: {},
    });
    expect((average.data as any).lines[0]).toMatchObject({ label: "Driver (avg, 2p)" });
    expect((average.data as any).lines[0].points).toEqual([{ x: "2026-08-10", y: 3 }]);
  });
});

describe("fairness metric", () => {
  it("computes population standard deviation across all people including zero-hour people", async () => {
    const result = await new FairnessMetric().calculate(buildWorkloadSchedule());
    const line = (result.data as any).lines[0];

    expect(line.label).toBe("Std Dev (all, 3p)");
    expect(line.points[0].x).toBe("2026-08-10");
    expect(line.points[0].y).toBeCloseTo(1.633, 3);
    expect(result.value).toBeCloseTo(1.633, 3);
  });

  it("computes fairness within selected capability members", async () => {
    const result = await new FairnessMetric().calculate(buildWorkloadSchedule(), undefined, {
      personIds: [],
      capabilityIds: [10],
      colorMap: {},
    });
    const line = (result.data as any).lines[0];

    expect(line.label).toBe("Driver (2p)");
    expect(line.points).toEqual([{ x: "2026-08-10", y: 1 }]);
  });
});

describe("workload spider metric", () => {
  it("calculates assignments, hours, and breaks for selected people", async () => {
    const result = await new WorkloadSpiderMetric().calculate(buildWorkloadSchedule(), undefined, {
      personIds: [1],
      capabilityIds: [],
      colorMap: {},
    });
    const radar = result.data as any;

    expect(radar.axes).toEqual(["Assignments", "Working Hours", "Breaks"]);
    expect(radar.datasets[0]).toMatchObject({ label: "Alice Able", values: [3, 4, 2] });
  });

  it("averages workload dimensions across capability members and overall population", async () => {
    const capability = await new WorkloadSpiderMetric().calculate(buildWorkloadSchedule(), undefined, {
      personIds: [],
      capabilityIds: [10],
      colorMap: {},
    });
    expect((capability.data as any).datasets[0]).toMatchObject({
      label: "Driver (avg, 2p)",
      values: [2.5, 3, 1.5],
    });

    const overall = await new WorkloadSpiderMetric().calculate(buildWorkloadSchedule());
    expect((overall.data as any).datasets[0]).toMatchObject({
      label: "Overall (avg, 3p)",
      values: [1.67, 2, 1],
    });
  });
});

describe("task type spider metrics", () => {
  it("excludes non-work task types from work metrics but retains task-type duration", async () => {
    const schedule = buildMetricScheduleData(
      [
        {
          id: 801,
          name: "Sleep shift",
          event_id: 1,
          template_id: 500,
          task_type_id: 300,
          date: "2026-08-10",
          final: {
            start_time: "00:00",
            end_time: "05:00",
            assigned_persons: [1],
          },
        },
        {
          id: 802,
          name: "Morning work",
          event_id: 1,
          template_id: 500,
          task_type_id: 100,
          date: "2026-08-10",
          final: {
            start_time: "08:00",
            end_time: "09:00",
            assigned_persons: [1],
          },
        },
      ] as any,
      people,
      capabilities,
      {},
      [
        {
          id: 100,
          name: "Shift",
          fatigue_score: 1,
          counts_towards_work_time: true,
        },
        {
          id: 300,
          name: "Sleep",
          fatigue_score: 0,
          counts_towards_work_time: false,
        },
      ] as any,
      undefined,
      templates,
    ).data;

    expect(
      calculatePersonHoursByDay(schedule).get("2026-08-10")?.get(1),
    ).toBe(1);

    const absolute = await new AbsoluteWorkingHoursMetric().calculate(schedule);
    expect(absolute.value).toBe(1);

    const streak = await new MaxWorkStreakMetric().calculate(
      schedule,
      undefined,
      {
        personIds: [1],
        capabilityIds: [],
        colorMap: {},
      },
    );
    expect((streak.data as any).lines[0].points[0].y).toBe(1);

    const taskTypeHours = await new TaskTypeHoursSpiderMetric().calculate(
      schedule,
      undefined,
      { personIds: [1], capabilityIds: [], colorMap: {} },
    );
    expect((taskTypeHours.data as any).axes).toEqual(["Shift", "Sleep"]);
    expect((taskTypeHours.data as any).datasets[0].values).toEqual([1, 5]);
  });

  it("calculates task-type counts per person, capability average, and overall average", async () => {
    const schedule = buildTaskTypeSchedule();

    const person = await new TaskTypeCountSpiderMetric().calculate(schedule, undefined, {
      personIds: [1],
      capabilityIds: [],
      colorMap: {},
    });
    expect((person.data as any).axes).toEqual(["Shift", "Transport"]);
    expect((person.data as any).datasets[0]).toMatchObject({ label: "Alice Able", values: [2, 1] });

    const capability = await new TaskTypeCountSpiderMetric().calculate(schedule, undefined, {
      personIds: [],
      capabilityIds: [10],
      colorMap: {},
    });
    expect((capability.data as any).datasets[0]).toMatchObject({
      label: "Driver (avg, 2p)",
      values: [1.5, 0.5],
    });

    const overall = await new TaskTypeCountSpiderMetric().calculate(schedule);
    expect((overall.data as any).datasets[0]).toMatchObject({
      label: "Overall (avg, 3p)",
      values: [1, 0.33],
    });
  });

  it("calculates task-type hours per person, capability average, and overall average", async () => {
    const schedule = buildTaskTypeSchedule();

    const person = await new TaskTypeHoursSpiderMetric().calculate(schedule, undefined, {
      personIds: [1],
      capabilityIds: [],
      colorMap: {},
    });
    expect((person.data as any).datasets[0]).toMatchObject({ label: "Alice Able", values: [3, 1] });

    const capability = await new TaskTypeHoursSpiderMetric().calculate(schedule, undefined, {
      personIds: [],
      capabilityIds: [10],
      colorMap: {},
    });
    expect((capability.data as any).datasets[0]).toMatchObject({
      label: "Driver (avg, 2p)",
      values: [2, 0.5],
    });

    const overall = await new TaskTypeHoursSpiderMetric().calculate(schedule);
    expect((overall.data as any).datasets[0]).toMatchObject({
      label: "Overall (avg, 3p)",
      values: [1.33, 0.33],
    });
  });
});

describe("max work streak metric", () => {
  it("merges gaps of fifteen minutes or less and splits larger gaps", async () => {
    const schedule = buildStreakSchedule();
    const result = await new MaxWorkStreakMetric().calculate(schedule, undefined, {
      personIds: [1],
      capabilityIds: [],
      colorMap: {},
    });

    expect((result.data as any).lines[0].points).toEqual([{ x: "2026-08-10", y: 2 }]);
    expect(result.value).toBe(2);
  });

  it("averages max streaks across capability members and overall population", async () => {
    const schedule = buildStreakSchedule();

    const capability = await new MaxWorkStreakMetric().calculate(schedule, undefined, {
      personIds: [],
      capabilityIds: [10],
      colorMap: {},
    });
    expect((capability.data as any).lines[0]).toMatchObject({
      label: "Driver (avg, 2p)",
      points: [{ x: "2026-08-10", y: 1.25 }],
    });

    const overall = await new MaxWorkStreakMetric().calculate(schedule);
    expect((overall.data as any).lines[0]).toMatchObject({
      label: "Avg Max Streak (3p)",
      points: [{ x: "2026-08-10", y: 0.83 }],
    });
  });
});

describe("fatigue metrics", () => {
  it("calculates event fatigue with task fatigue and break recovery", async () => {
    const schedule = buildWorkloadSchedule();

    const selectedPerson = await new FatigueTimelineMetric().calculate(schedule, undefined, {
      personIds: [1],
      capabilityIds: [],
      colorMap: {},
    });
    expect((selectedPerson.data as any).lines[0].points).toEqual([{ x: "2026-08-10", y: 234 }]);

    const capability = await new FatigueTimelineMetric().calculate(schedule, undefined, {
      personIds: [],
      capabilityIds: [10],
      colorMap: {},
    });
    expect((capability.data as any).lines[0].points).toEqual([{ x: "2026-08-10", y: 175.5 }]);

    const overall = await new FatigueTimelineMetric().calculate(schedule);
    expect((overall.data as any).lines[0].points).toEqual([{ x: "2026-08-10", y: 117 }]);
  });

  it("keeps after-midnight fatigue day-view points in chronological working-day order", async () => {
    const { data } = buildMetricScheduleData(
      [
        {
          id: 1,
          name: "Late shift",
          event_id: 1,
          template_id: 500,
          task_type_id: 100,
          date: "2026-08-10",
          is_floating: false,
          is_transfer: false,
          final: { start_time: "23:00", end_time: "24:00", assigned_persons: [1] },
        },
        {
          id: 2,
          name: "After midnight",
          event_id: 1,
          template_id: 500,
          task_type_id: 100,
          date: "2026-08-11",
          is_floating: false,
          is_transfer: false,
          final: { start_time: "00:30", end_time: "01:00", assigned_persons: [1] },
        },
      ] as any[],
      people,
      capabilities,
      {},
      taskTypes,
      ["2026-08-10"],
      templates,
      { 1: { offsetHour: 4 } },
    );

    const result = await new FatigueTimelineMetric().calculate(data, undefined, {
      personIds: [1],
      capabilityIds: [],
      colorMap: {},
      timeAggregation: "day",
    });

    expect((result.data as any).xOrder).toEqual(["23:00", "00:00", "00:30", "01:00"]);
  });

  it("computes CFII as each person fatigue minus the daily group mean", async () => {
    const result = await new CFIIMetric().calculate(buildWorkloadSchedule());
    const points = (result.data as any).data;

    expect(points).toEqual([
      { x: "2026-08-10", y: "Alice Able", value: 117 },
      { x: "2026-08-10", y: "Bob Baker", value: 0 },
      { x: "2026-08-10", y: "Clara Calm", value: -117 },
    ]);
    expect(result.value).toBe(117);
  });
});

describe("metrics schedule diagnostics and breakdowns", () => {
  it("filters missing people while preserving diagnostic counts and assignment sources", () => {
    const { data, diagnostics } = buildMetricScheduleData(
      [
        {
          id: 101,
          name: "Known and unknown people",
          event_id: 1,
          template_id: 500,
          task_type_id: 100,
          date: "2026-08-10",
          is_floating: false,
          is_transfer: false,
          final: {
            start_time: "09:00",
            end_time: "10:00",
            assigned_persons: [1, 999],
            field_assignments: { people: [2, 999] },
          },
        },
        {
          id: 102,
          name: "Missing time",
          event_id: 1,
          template_id: 500,
          task_type_id: 100,
          date: "2026-08-10",
          is_floating: false,
          is_transfer: false,
          field_values: { people: [1] },
        },
      ] as any[],
      people,
      capabilities,
      {},
      taskTypes,
      ["2026-08-10"],
      templates,
    );

    expect(diagnostics).toMatchObject({
      includedTasks: 1,
      skippedMissingTimes: 1,
      missingPersonReferences: 1,
    });
    expect(data.tasks[0].person_ids).toEqual([1, 2]);
    expect(data.tasks[0].person_assignment_sources).toEqual({
      1: ["assigned_persons"],
      2: ["field:people"],
      999: ["assigned_persons", "field:people"],
    });
  });

  it("returns max-hour violation task breakdowns with source and assignment provenance", () => {
    const { data } = buildMetricScheduleData(
      [
        {
          id: 103,
          name: "Long final task",
          event_id: 1,
          template_id: 500,
          task_type_id: 100,
          date: "2026-08-10",
          is_floating: false,
          is_transfer: false,
          final: { start_time: "09:00", end_time: "12:00", assigned_persons: [1] },
        },
      ] as any[],
      people,
      capabilities,
      {},
      taskTypes,
      ["2026-08-10"],
      templates,
    );

    expect(findMaxHoursViolationBreakdowns(data)).toEqual([
      {
        personId: 1,
        personName: "Alice Able",
        date: "2026-08-10",
        hours: 3,
        maxHours: 2.5,
        tasks: [
          {
            taskId: "103",
            taskName: "Long final task",
            date: "2026-08-10",
            startTime: "2026-08-10T09:00:00",
            endTime: "2026-08-10T12:00:00",
            durationHours: 3,
            source: "final",
            assignmentSource: ["assigned_persons"],
          },
        ],
      },
    ]);
  });
});

describe("additional working-hours edge cases", () => {
  it("capability workload counts only the assigned people who hold that capability", async () => {
    const { data } = buildMetricScheduleData(
      [
        {
          id: 201,
          name: "Mixed capability task",
          event_id: 1,
          template_id: 500,
          task_type_id: 100,
          date: "2026-08-10",
          is_floating: false,
          is_transfer: false,
          final: { start_time: "09:00", end_time: "11:00", assigned_persons: [1, 3] },
        },
      ] as any[],
      people,
      capabilities,
      {},
      taskTypes,
      ["2026-08-10"],
      templates,
    );

    const absolute = await new AbsoluteWorkingHoursMetric().calculate(data, undefined, {
      personIds: [],
      capabilityIds: [10],
      colorMap: {},
    });
    expect((absolute.data as any).lines[0].points).toEqual([{ x: "2026-08-10", y: 2 }]);

    const average = await new AverageWorkingHoursMetric().calculate(data, undefined, {
      personIds: [],
      capabilityIds: [10],
      colorMap: {},
    });
    expect((average.data as any).lines[0].points).toEqual([{ x: "2026-08-10", y: 1 }]);
  });

  it("selected people with no work still render all event days as zero", async () => {
    const result = await new AbsoluteWorkingHoursMetric().calculate(buildWorkloadSchedule(), undefined, {
      personIds: [3],
      capabilityIds: [],
      colorMap: {},
    });

    expect((result.data as any).lines[0]).toMatchObject({
      label: "Clara Calm",
      points: [{ x: "2026-08-10", y: 0 }],
    });
    expect(result.value).toBe(0);
  });
});

describe("additional max working-hours edge cases", () => {
  it("reports no scheduled hours for an event with dates but no timed work", async () => {
    const { data } = buildMetricScheduleData(
      [],
      people,
      capabilities,
      {},
      taskTypes,
      ["2026-08-10", "2026-08-11"],
      templates,
    );

    const result = await new MaxWorkingHoursMetric().calculate(data);

    expect(result.value).toBe(0);
    expect(result.label).toBe("No scheduled hours");
    expect((result.data as any).lines[0].points).toEqual([
      { x: "2026-08-10", y: 0 },
      { x: "2026-08-11", y: 0 },
    ]);
  });

  it("does not create fake limit lines for selected people without configured limits", async () => {
    const result = await new MaxWorkingHoursMetric().calculate(buildWorkloadSchedule(), undefined, {
      personIds: [2],
      capabilityIds: [],
      colorMap: {},
    });

    expect((result.data as any).lines).toHaveLength(1);
    expect((result.data as any).lines[0]).toMatchObject({
      label: "Bob Baker",
      points: [{ x: "2026-08-10", y: 2 }],
    });
  });
});

describe("additional fairness edge cases", () => {
  it("emits zero fairness for event days with no assignments", async () => {
    const { data } = buildMetricScheduleData(
      [
        {
          id: 301,
          name: "One-day task",
          event_id: 1,
          template_id: 500,
          task_type_id: 100,
          date: "2026-08-10",
          is_floating: false,
          is_transfer: false,
          final: { start_time: "09:00", end_time: "10:00", assigned_persons: [1] },
        },
      ] as any[],
      people,
      capabilities,
      {},
      taskTypes,
      ["2026-08-10", "2026-08-11"],
      templates,
    );

    const result = await new FairnessMetric().calculate(data);
    expect((result.data as any).lines[0].points).toEqual([
      { x: "2026-08-10", y: 0.471 },
      { x: "2026-08-11", y: 0 },
    ]);
  });

  it("handles selected capabilities with no members without crashing", async () => {
    const result = await new FairnessMetric().calculate(buildWorkloadSchedule(), undefined, {
      personIds: [],
      capabilityIds: [20],
      colorMap: {},
    });

    expect(result.value).toBe(0);
    expect(result.label).toBe("0 groups");
    expect((result.data as any).lines).toEqual([]);
  });
});

describe("additional workload spider edge cases", () => {
  it("does not count overlapping tasks as breaks and separates breaks by working day", async () => {
    const schedule = buildOverlapBreakSchedule();
    const result = await new WorkloadSpiderMetric().calculate(schedule, undefined, {
      personIds: [1],
      capabilityIds: [],
      colorMap: {},
    });

    expect((result.data as any).datasets[0]).toMatchObject({
      label: "Alice Able",
      values: [4, 4.5, 1],
    });
  });
});

describe("additional task-type spider edge cases", () => {
  it("returns a calm empty radar when task-type metadata is unavailable", async () => {
    const { data } = buildMetricScheduleData(
      [
        {
          id: 401,
          name: "Untyped task",
          event_id: 1,
          template_id: 500,
          task_type_id: 100,
          date: "2026-08-10",
          is_floating: false,
          is_transfer: false,
          final: { start_time: "09:00", end_time: "10:00", assigned_persons: [1] },
        },
      ] as any[],
      people,
      capabilities,
      {},
      [],
      ["2026-08-10"],
      templates,
    );

    const count = await new TaskTypeCountSpiderMetric().calculate(data);
    expect(count).toMatchObject({ value: 0, label: "No task types" });
    expect(count.data).toEqual({ type: "radar", axes: ["-"], datasets: [] });

    const hours = await new TaskTypeHoursSpiderMetric().calculate(data);
    expect(hours).toMatchObject({ value: 0, label: "No task types" });
    expect(hours.data).toEqual({ type: "radar", axes: ["-"], datasets: [] });
  });
});

describe("additional streak and fatigue edge cases", () => {
  it("max streak merges overlapping tasks and an exact fifteen-minute gap into one streak", async () => {
    const schedule = buildOverlappingStreakSchedule();
    const result = await new MaxWorkStreakMetric().calculate(schedule, undefined, {
      personIds: [1],
      capabilityIds: [],
      colorMap: {},
    });

    expect((result.data as any).lines[0].points).toEqual([{ x: "2026-08-10", y: 3 }]);
    expect(result.value).toBe(3);
  });

  it("fatigue event view applies recovery only for gaps of at least thirty minutes", async () => {
    const schedule = buildFatigueThresholdSchedule();
    const result = await new FatigueTimelineMetric().calculate(schedule, undefined, {
      personIds: [1],
      capabilityIds: [],
      colorMap: {},
    });

    expect((result.data as any).lines[0].points).toEqual([{ x: "2026-08-10", y: 177 }]);
    expect(result.value).toBe(177);
  });

  it("fatigue day view gives a selected person with no tasks a flat line over the active day window", async () => {
    const result = await new FatigueTimelineMetric().calculate(buildWorkloadSchedule(), undefined, {
      personIds: [3],
      capabilityIds: [],
      colorMap: {},
      timeAggregation: "day",
    });

    expect((result.data as any).lines[0]).toMatchObject({
      label: "Clara Calm",
      points: [
        { x: "10:00", y: 0 },
        { x: "18:00", y: 0 },
      ],
    });
  });

  it("CFII emits zero imbalance for empty event days", async () => {
    const { data } = buildMetricScheduleData(
      [],
      people,
      capabilities,
      {},
      taskTypes,
      ["2026-08-10"],
      templates,
    );

    const result = await new CFIIMetric().calculate(data);
    expect((result.data as any).data).toEqual([
      { x: "2026-08-10", y: "Alice Able", value: 0 },
      { x: "2026-08-10", y: "Bob Baker", value: 0 },
      { x: "2026-08-10", y: "Clara Calm", value: 0 },
    ]);
    expect(result.value).toBe(0);
  });
});
describe("MetricResourceSelector", () => {
  it("renders duplicate persisted filters once without React key warnings", () => {
    const errorSpy = vi.spyOn(console, "error").mockImplementation(() => {});

    render(
      <MetricResourceSelector
        people={schedulePeople()}
        capabilities={capabilities as any}
        selectedPersonIds={[1, 1]}
        selectedCapabilityIds={[10, 10]}
        colorMap={{}}
        onAddPerson={vi.fn()}
        onRemovePerson={vi.fn()}
        onAddCapability={vi.fn()}
        onRemoveCapability={vi.fn()}
        onColorChange={vi.fn()}
      />,
    );

    expect(screen.getByText("Alice Able")).toBeInTheDocument();
    expect(screen.getByText("Driver")).toBeInTheDocument();
    expect(screen.getAllByText("Alice Able")).toHaveLength(1);
    expect(screen.getAllByText("Driver")).toHaveLength(1);
    expect(errorSpy).not.toHaveBeenCalledWith(
      expect.stringContaining("Each child in a list should have a unique"),
    );

    errorSpy.mockRestore();
  });
});


function buildTaskTypeSchedule() {
  return buildMetricScheduleData(
    [
      {
        id: 10,
        name: "Alice setup",
        event_id: 1,
        template_id: 500,
        task_type_id: 100,
        date: "2026-08-10",
        is_floating: false,
        is_transfer: false,
        final: { start_time: "09:00", end_time: "11:00", assigned_persons: [1] },
      },
      {
        id: 11,
        name: "Alice transport",
        event_id: 1,
        template_id: 500,
        task_type_id: 200,
        date: "2026-08-10",
        is_floating: false,
        is_transfer: false,
        final: { start_time: "12:00", end_time: "13:00", assigned_persons: [1] },
      },
      {
        id: 12,
        name: "Shared setup",
        event_id: 1,
        template_id: 500,
        task_type_id: 100,
        date: "2026-08-10",
        is_floating: false,
        is_transfer: false,
        final: { start_time: "14:00", end_time: "15:00", assigned_persons: [1, 2] },
      },
    ] as any[],
    people,
    capabilities,
    {},
    taskTypes,
    ["2026-08-10"],
    templates,
  ).data;
}

function buildStreakSchedule() {
  return buildMetricScheduleData(
    [
      {
        id: 20,
        name: "Alice first streak part",
        event_id: 1,
        template_id: 500,
        task_type_id: 100,
        date: "2026-08-10",
        is_floating: false,
        is_transfer: false,
        final: { start_time: "09:00", end_time: "10:00", assigned_persons: [1] },
      },
      {
        id: 21,
        name: "Alice exact threshold gap",
        event_id: 1,
        template_id: 500,
        task_type_id: 100,
        date: "2026-08-10",
        is_floating: false,
        is_transfer: false,
        final: { start_time: "10:15", end_time: "11:00", assigned_persons: [1] },
      },
      {
        id: 22,
        name: "Alice split by larger gap",
        event_id: 1,
        template_id: 500,
        task_type_id: 100,
        date: "2026-08-10",
        is_floating: false,
        is_transfer: false,
        final: { start_time: "11:16", end_time: "12:00", assigned_persons: [1] },
      },
      {
        id: 23,
        name: "Bob short streak",
        event_id: 1,
        template_id: 500,
        task_type_id: 100,
        date: "2026-08-10",
        is_floating: false,
        is_transfer: false,
        final: { start_time: "09:00", end_time: "09:30", assigned_persons: [2] },
      },
    ] as any[],
    people,
    capabilities,
    {},
    taskTypes,
    ["2026-08-10"],
    templates,
  ).data;
}
function buildOverlapBreakSchedule() {
  return buildMetricScheduleData(
    [
      {
        id: 501,
        name: "Overlap A",
        event_id: 1,
        template_id: 500,
        task_type_id: 100,
        date: "2026-08-10",
        is_floating: false,
        is_transfer: false,
        final: { start_time: "09:00", end_time: "10:00", assigned_persons: [1] },
      },
      {
        id: 502,
        name: "Overlap B",
        event_id: 1,
        template_id: 500,
        task_type_id: 100,
        date: "2026-08-10",
        is_floating: false,
        is_transfer: false,
        final: { start_time: "09:30", end_time: "11:00", assigned_persons: [1] },
      },
      {
        id: 503,
        name: "Next day first",
        event_id: 1,
        template_id: 500,
        task_type_id: 100,
        date: "2026-08-11",
        is_floating: false,
        is_transfer: false,
        final: { start_time: "09:00", end_time: "10:00", assigned_persons: [1] },
      },
      {
        id: 504,
        name: "Next day second",
        event_id: 1,
        template_id: 500,
        task_type_id: 100,
        date: "2026-08-11",
        is_floating: false,
        is_transfer: false,
        final: { start_time: "11:00", end_time: "12:00", assigned_persons: [1] },
      },
    ] as any[],
    people,
    capabilities,
    {},
    taskTypes,
    ["2026-08-10", "2026-08-11"],
    templates,
  ).data;
}

function buildOverlappingStreakSchedule() {
  return buildMetricScheduleData(
    [
      {
        id: 601,
        name: "Overlap streak start",
        event_id: 1,
        template_id: 500,
        task_type_id: 100,
        date: "2026-08-10",
        is_floating: false,
        is_transfer: false,
        final: { start_time: "09:00", end_time: "10:00", assigned_persons: [1] },
      },
      {
        id: 602,
        name: "Overlap streak extension",
        event_id: 1,
        template_id: 500,
        task_type_id: 100,
        date: "2026-08-10",
        is_floating: false,
        is_transfer: false,
        final: { start_time: "09:30", end_time: "11:00", assigned_persons: [1] },
      },
      {
        id: 603,
        name: "Exact gap extension",
        event_id: 1,
        template_id: 500,
        task_type_id: 100,
        date: "2026-08-10",
        is_floating: false,
        is_transfer: false,
        final: { start_time: "11:15", end_time: "12:00", assigned_persons: [1] },
      },
    ] as any[],
    people,
    capabilities,
    {},
    taskTypes,
    ["2026-08-10"],
    templates,
  ).data;
}

function buildFatigueThresholdSchedule() {
  return buildMetricScheduleData(
    [
      {
        id: 701,
        name: "Fatigue first",
        event_id: 1,
        template_id: 500,
        task_type_id: 100,
        date: "2026-08-10",
        is_floating: false,
        is_transfer: false,
        final: { start_time: "09:00", end_time: "10:00", assigned_persons: [1] },
      },
      {
        id: 702,
        name: "Fatigue no recovery",
        event_id: 1,
        template_id: 500,
        task_type_id: 100,
        date: "2026-08-10",
        is_floating: false,
        is_transfer: false,
        final: { start_time: "10:29", end_time: "11:29", assigned_persons: [1] },
      },
      {
        id: 703,
        name: "Fatigue recovery threshold",
        event_id: 1,
        template_id: 500,
        task_type_id: 100,
        date: "2026-08-10",
        is_floating: false,
        is_transfer: false,
        final: { start_time: "11:59", end_time: "12:59", assigned_persons: [1] },
      },
    ] as any[],
    people,
    capabilities,
    {},
    taskTypes,
    ["2026-08-10"],
    templates,
  ).data;
}function schedulePeople() {
  return people.map((person) => ({
    id: person.id,
    name: `${person.first_name} ${person.last_name}`,
    first_name: person.first_name,
    last_name: person.last_name,
    email: person.email,
    capabilities: person.capabilities,
    max_hours_per_day: person.max_hours_per_day,
  }));
}







