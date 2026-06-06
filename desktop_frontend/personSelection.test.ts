import { describe, expect, it } from "vitest";
import {
  dedupePersonSelectionIds,
  mergePersonSelectionIds,
  removePersonSelectionIds,
} from "@/lib/personSelection";

describe("person selection helpers", () => {
  it("adds only missing group members when a group is imported again", () => {
    const teamMemberIds = [1, 2, 3];
    const initiallyImported = mergePersonSelectionIds([], teamMemberIds);
    const afterManualRemoval = removePersonSelectionIds(initiallyImported, [2]);

    expect(afterManualRemoval).toEqual([1, 3]);
    expect(mergePersonSelectionIds(afterManualRemoval, teamMemberIds)).toEqual([
      1, 3, 2,
    ]);
  });

  it("treats a fully imported group as a no-op instead of duplicating members", () => {
    expect(mergePersonSelectionIds([1, 2, 3], [1, 2, 3])).toEqual([1, 2, 3]);
  });

  it("deduplicates mixed object and scalar member entries before saving", () => {
    expect(
      dedupePersonSelectionIds([
        { type: "person", id: 1 },
        1,
        { type: "person", id: "2" },
        2,
        { id: 3 },
      ]),
    ).toEqual([1, 2, 3]);
  });
});
