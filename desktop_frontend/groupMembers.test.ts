import { describe, expect, it } from "vitest";
import {
  getDirectPersonIdsFromMembers,
  getIncludedGroupIdsFromMembers,
  mergeGroupMemberSelections,
  normaliseGroupMembers,
  removeGroupMemberSelection,
  resolveGroupAssignmentForTask,
  resolveGroupMembers,
  wouldCreateCircularGroupReference,
} from "@/lib/groupMembers";
import type { Group } from "@/lib/api";

const group = (id: number, name: string, members: Group["members"]): Group => ({
  id,
  event_id: 1,
  name,
  attributes: {},
  members,
});

const resolveAvailability = ({
  unavailabilities,
  taskDate = "2026-07-10",
  selectedWorkingDate = "2026-07-10",
  taskStart = "09:00",
  taskEnd = "10:00",
  workingDayBoundaryOffsetHour = 0,
  direct = false,
}: {
  unavailabilities: unknown[];
  taskDate?: string;
  selectedWorkingDate?: string | null;
  taskStart?: string | number;
  taskEnd?: string | number;
  workingDayBoundaryOffsetHour?: number;
  direct?: boolean;
}) => {
  const availabilityGroup = group(20, "Operations", [
    { type: "person", id: 1 },
  ]);
  return resolveGroupAssignmentForTask({
    value: direct
      ? [{ type: "person", id: 1 }]
      : [{ type: "group", id: availabilityGroup.id }],
    groups: [availabilityGroup],
    persons: [
      {
        id: 1,
        global_data: { unavailabilities },
      },
    ],
    taskDate,
    selectedWorkingDate,
    workingDayBoundaryOffsetHour,
    taskStart,
    taskEnd,
  });
};

describe("group member helpers", () => {
  it("keeps direct people and included groups as separate member types", () => {
    const members = normaliseGroupMembers([
      { type: "person", id: "1" },
      { type: "person", id: 1 },
      { type: "group", id: "10" },
      { type: "group", id: 10 },
    ]);

    expect(members).toEqual([
      { type: "person", id: 1 },
      { type: "group", id: 10 },
    ]);
    expect(getDirectPersonIdsFromMembers(members)).toEqual([1]);
    expect(getIncludedGroupIdsFromMembers(members)).toEqual([10]);
  });

  it("resolves a group that includes another group", () => {
    const groups = [
      group(10, "Core Team", [
        { type: "person", id: 2 },
        { type: "person", id: 3 },
      ]),
      group(20, "OrgaTeam", [
        { type: "person", id: 1 },
        { type: "group", id: 10 },
      ]),
    ];

    expect(resolveGroupMembers(20, groups).personIds).toEqual([1, 2, 3]);
  });

  it("deduplicates people across direct and nested group membership", () => {
    const groups = [
      group(10, "Core Team", [
        { type: "person", id: 1 },
        { type: "person", id: 2 },
      ]),
      group(11, "Chairs", [
        { type: "person", id: 2 },
        { type: "person", id: 3 },
      ]),
      group(20, "OrgaTeam", [
        { type: "person", id: 1 },
        { type: "group", id: 10 },
        { type: "group", id: 11 },
      ]),
    ];

    expect(resolveGroupMembers(20, groups).personIds).toEqual([1, 2, 3]);
  });

  it("supports nested group resolution with stable ordering", () => {
    const groups = [
      group(1, "Level 1", [{ type: "person", id: 4 }]),
      group(2, "Level 2", [
        { type: "person", id: 3 },
        { type: "group", id: 1 },
      ]),
      group(3, "Level 3", [
        { type: "person", id: 2 },
        { type: "group", id: 2 },
      ]),
    ];

    expect(resolveGroupMembers(3, groups).personIds).toEqual([2, 3, 4]);
  });

  it("warns about missing included groups without crashing", () => {
    const groups = [
      group(20, "OrgaTeam", [
        { type: "person", id: 1 },
        { type: "group", id: 404 },
      ]),
    ];

    const resolved = resolveGroupMembers(20, groups);

    expect(resolved.personIds).toEqual([1]);
    expect(resolved.warnings).toContain("This group no longer exists.");
  });

  it("detects circular references before saving a group", () => {
    const groups = [
      group(10, "Core Team", [{ type: "group", id: 20 }]),
      group(20, "OrgaTeam", []),
    ];

    expect(wouldCreateCircularGroupReference(20, [10], groups)).toBe(true);
    expect(wouldCreateCircularGroupReference(20, [], groups)).toBe(false);
  });

  it("stores direct people and group references together for live task assignments", () => {
    const selection = mergeGroupMemberSelections(
      [{ type: "person", id: 1 }],
      [
        { type: "group", id: 20 },
        { type: "group", id: 20 },
      ],
    );

    expect(selection).toEqual([
      { type: "person", id: 1 },
      { type: "group", id: 20 },
    ]);
  });

  it("removes a group chip without removing direct people", () => {
    const selection = [
      { type: "person" as const, id: 1 },
      { type: "group" as const, id: 20 },
    ];

    expect(removeGroupMemberSelection(selection, "group", 20)).toEqual([
      { type: "person", id: 1 },
    ]);
  });

  it("propagates group changes because task assignments keep the group reference", () => {
    const groups = [
      group(10, "Core Team", [{ type: "person", id: 2 }]),
      group(20, "OrgaTeam", [
        { type: "person", id: 1 },
        { type: "group", id: 10 },
      ]),
    ];
    const taskAssignment = [{ type: "group" as const, id: 20 }];

    expect(normaliseGroupMembers(taskAssignment)).toEqual([
      { type: "group", id: 20 },
    ]);
    expect(resolveGroupMembers(20, groups).personIds).toEqual([1, 2]);

    const changedGroups = groups.map((candidate) =>
      candidate.id === 10
        ? group(10, "Core Team", [
            { type: "person", id: 2 },
            { type: "person", id: 3 },
          ])
        : candidate,
    );

    expect(resolveGroupMembers(20, changedGroups).personIds).toEqual([1, 2, 3]);
  });
});

describe("group member availability", () => {
  it("does not move one-off unavailability from the next day onto the task", () => {
    const resolved = resolveAvailability({
      unavailabilities: [
        { from: "2026-07-11T09:00", to: "2026-07-11T10:00" },
      ],
    });

    expect(resolved.personIds).toEqual([1]);
    expect(resolved.excludedPersons).toEqual([]);
  });

  it("does not move one-off unavailability from the previous day onto the task", () => {
    const resolved = resolveAvailability({
      unavailabilities: [
        { from: "2026-07-09T09:00", to: "2026-07-09T10:00" },
      ],
    });

    expect(resolved.personIds).toEqual([1]);
    expect(resolved.excludedPersons).toEqual([]);
  });

  it("excludes a group member for same-day unavailability and labels its date", () => {
    const resolved = resolveAvailability({
      unavailabilities: [
        { from: "2026-07-10T09:15", to: "2026-07-10T09:45" },
      ],
    });

    expect(resolved.personIds).toEqual([]);
    expect(resolved.excludedPersons[0]).toMatchObject({
      person_id: 1,
      unavailable_from: "10.07.2026 09:15",
      unavailable_to: "10.07.2026 09:45",
    });
  });

  it("uses both dates for a multi-day unavailability period", () => {
    const resolved = resolveAvailability({
      unavailabilities: [
        { from: "2026-07-10T08:00", to: "2026-07-11T10:00" },
      ],
      taskStart: "20:00",
      taskEnd: "21:00",
    });

    expect(resolved.personIds).toEqual([]);
  });

  it("matches the next actual date in an overnight working-day tail", () => {
    const resolved = resolveAvailability({
      unavailabilities: [
        { from: "2026-07-11T01:00", to: "2026-07-11T02:00" },
      ],
      taskDate: "2026-07-11",
      taskStart: "01:15",
      taskEnd: "01:45",
      workingDayBoundaryOffsetHour: 4,
    });

    expect(resolved.personIds).toEqual([]);
  });

  it("does not apply the task date twice to already-linear overnight times", () => {
    const resolved = resolveAvailability({
      unavailabilities: [
        { from: "2026-07-11T01:00", to: "2026-07-11T02:00" },
      ],
      taskDate: "2026-07-11",
      taskStart: 25 * 60 + 15,
      taskEnd: 25 * 60 + 45,
      workingDayBoundaryOffsetHour: 4,
    });

    expect(resolved.personIds).toEqual([]);
  });

  it("infers the working date when an overnight calendar conversion has no selected day", () => {
    const resolved = resolveAvailability({
      unavailabilities: [
        { from: "2026-07-11T01:00", to: "2026-07-11T02:00" },
      ],
      selectedWorkingDate: null,
      taskDate: "2026-07-11",
      taskStart: 25 * 60 + 15,
      taskEnd: 25 * 60 + 45,
      workingDayBoundaryOffsetHour: 4,
    });

    expect(resolved.personIds).toEqual([]);
  });

  it("continues to apply time-only recurring unavailability", () => {
    const resolved = resolveAvailability({
      unavailabilities: [{ start: "01:00", end: "02:00" }],
      taskDate: "2026-07-11",
      taskStart: "01:15",
      taskEnd: "01:45",
      workingDayBoundaryOffsetHour: 4,
    });

    expect(resolved.personIds).toEqual([]);
  });

  it("keeps explicit person assignments even when the person is unavailable", () => {
    const resolved = resolveAvailability({
      unavailabilities: [
        { from: "2026-07-10T09:00", to: "2026-07-10T10:00" },
      ],
      direct: true,
    });

    expect(resolved.personIds).toEqual([1]);
    expect(resolved.excludedPersons).toEqual([]);
  });
});
