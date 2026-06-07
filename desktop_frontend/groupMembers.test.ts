import { describe, expect, it } from "vitest";
import {
  getDirectPersonIdsFromMembers,
  getIncludedGroupIdsFromMembers,
  mergeGroupMemberSelections,
  normaliseGroupMembers,
  removeGroupMemberSelection,
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
