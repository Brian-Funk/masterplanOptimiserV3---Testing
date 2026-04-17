/**
 * Tests for dateFormat utility functions.
 */
import { describe, it, expect } from "vitest";
import {
  formatDateShort,
  formatDateWithWeekday,
  formatDateLong,
  formatDateTime,
} from "@/lib/dateFormat";

describe("formatDateShort", () => {
  it("formats YYYY-MM-DD as DD.MM.YY", () => {
    expect(formatDateShort("2026-08-01")).toBe("01.08.26");
  });

  it("formats ISO datetime string", () => {
    expect(formatDateShort("2026-12-25T14:30:00")).toBe("25.12.26");
  });

  it("pads single-digit day and month", () => {
    expect(formatDateShort("2026-01-05")).toBe("05.01.26");
  });
});

describe("formatDateWithWeekday", () => {
  it("includes short weekday", () => {
    // 2026-08-01 is a Saturday
    const result = formatDateWithWeekday("2026-08-01");
    expect(result).toMatch(
      /^(Mon|Tue|Wed|Thu|Fri|Sat|Sun), \d{2}\.\d{2}\.\d{2}$/,
    );
  });
});

describe("formatDateLong", () => {
  it("includes long weekday", () => {
    const result = formatDateLong("2026-08-01");
    // Should be like "Saturday, 01.08.26"
    expect(result).toMatch(
      /^(Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday), \d{2}\.\d{2}\.\d{2}$/,
    );
  });
});

describe("formatDateTime", () => {
  it("formats datetime as DD.MM.YY HH:MM", () => {
    const result = formatDateTime("2026-08-01T14:30:00");
    expect(result).toBe("01.08.26 14:30");
  });

  it("pads hours and minutes", () => {
    const result = formatDateTime("2026-01-05T08:05:00");
    expect(result).toBe("05.01.26 08:05");
  });
});
