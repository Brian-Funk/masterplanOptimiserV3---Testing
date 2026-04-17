/**
 * Tests for gcalColors — Google Calendar colour palette utilities.
 */
import { describe, it, expect } from "vitest";
import {
  GCAL_COLOR_META,
  GCAL_PALETTE,
  sortedGcalColors,
  gcalColorLabel,
} from "@/lib/gcalColors";
import type { GCalColor } from "@/lib/gcalColors";

describe("GCAL_COLOR_META", () => {
  it("has 11 colour entries", () => {
    expect(Object.keys(GCAL_COLOR_META)).toHaveLength(11);
  });

  it("each entry has label, order, background, and foreground", () => {
    for (const [, meta] of Object.entries(GCAL_COLOR_META)) {
      expect(meta).toHaveProperty("label");
      expect(meta).toHaveProperty("order");
      expect(meta).toHaveProperty("background");
      expect(meta).toHaveProperty("foreground");
      expect(typeof meta.label).toBe("string");
      expect(typeof meta.order).toBe("number");
    }
  });

  it("Tomato is id 11 with #D50000", () => {
    expect(GCAL_COLOR_META["11"].label).toBe("Tomato");
    expect(GCAL_COLOR_META["11"].background).toBe("#D50000");
  });

  it("Banana is id 5 with black foreground", () => {
    expect(GCAL_COLOR_META["5"].label).toBe("Banana");
    expect(GCAL_COLOR_META["5"].foreground).toBe("#000000");
  });
});

describe("GCAL_PALETTE", () => {
  it("has 11 colours", () => {
    expect(GCAL_PALETTE).toHaveLength(11);
  });

  it("is sorted by display order (Tomato first, Graphite last)", () => {
    expect(GCAL_PALETTE[0].id).toBe("11"); // Tomato (order 0)
    expect(GCAL_PALETTE[10].id).toBe("8"); // Graphite (order 10)
  });

  it("each entry has id, background, foreground", () => {
    for (const color of GCAL_PALETTE) {
      expect(color).toHaveProperty("id");
      expect(color).toHaveProperty("background");
      expect(color).toHaveProperty("foreground");
    }
  });
});

describe("sortedGcalColors", () => {
  it("sorts colours by display order", () => {
    const unsorted: GCalColor[] = [
      { id: "8", background: "#616161", foreground: "#FFFFFF" }, // Graphite (order 10)
      { id: "11", background: "#D50000", foreground: "#FFFFFF" }, // Tomato (order 0)
      { id: "7", background: "#039BE5", foreground: "#FFFFFF" }, // Peacock (order 6)
    ];

    const sorted = sortedGcalColors(unsorted);
    expect(sorted[0].id).toBe("11"); // Tomato first
    expect(sorted[1].id).toBe("7"); // Peacock second
    expect(sorted[2].id).toBe("8"); // Graphite last
  });

  it("does not mutate the original array", () => {
    const original: GCalColor[] = [
      { id: "8", background: "#616161", foreground: "#FFFFFF" },
      { id: "11", background: "#D50000", foreground: "#FFFFFF" },
    ];
    const copy = [...original];
    sortedGcalColors(original);
    expect(original).toEqual(copy);
  });

  it("puts unknown IDs at the end", () => {
    const colors: GCalColor[] = [
      { id: "unknown", background: "#000", foreground: "#FFF" },
      { id: "11", background: "#D50000", foreground: "#FFFFFF" },
    ];
    const sorted = sortedGcalColors(colors);
    expect(sorted[0].id).toBe("11");
    expect(sorted[1].id).toBe("unknown");
  });
});

describe("gcalColorLabel", () => {
  it("returns label for known ID", () => {
    expect(gcalColorLabel("11")).toBe("Tomato");
    expect(gcalColorLabel("5")).toBe("Banana");
    expect(gcalColorLabel("8")).toBe("Graphite");
  });

  it("returns fallback for unknown ID", () => {
    expect(gcalColorLabel("99")).toBe("Colour 99");
    expect(gcalColorLabel("xyz")).toBe("Colour xyz");
  });
});
