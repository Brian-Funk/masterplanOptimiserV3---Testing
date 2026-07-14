import { describe, expect, it } from "vitest";

import {
  getPublicScheduleItemsForView,
  getPublicScheduleViewsForDate,
} from "@/lib/publicScheduleViews";

const views = [
  { id: "10", name: "Delegates", sort_order: 0 },
  { id: "11", name: "Officials", sort_order: 1 },
];

const items = [
  {
    date: "2026-08-01",
    category_id: 10,
    start_time: "09:00",
    sort_order: 0,
    title: "Delegates briefing",
  },
  {
    date: "2026-08-02",
    working_date: "2026-08-01",
    category_id: 11,
    start_time: "01:00",
    sort_order: 0,
    title: "Officials briefing",
  },
];

describe("public schedule view filtering", () => {
  it("shows only schedule views populated on the selected date", () => {
    expect(getPublicScheduleViewsForDate(views, items, "2026-08-01")).toEqual([
      views[0],
      views[1],
    ]);
  });

  it("returns sorted items for the selected view and date", () => {
    expect(getPublicScheduleItemsForView(items, "2026-08-01", "11")).toEqual([
      items[1],
    ]);
    expect(getPublicScheduleItemsForView(items, "2026-08-02", "11")).toEqual([]);
  });
});
