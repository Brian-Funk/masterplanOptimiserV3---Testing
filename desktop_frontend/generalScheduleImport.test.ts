import { describe, expect, it } from "vitest";

import {
  GENERAL_SCHEDULE_IMPORT_HEADER,
  parseGeneralScheduleSpreadsheet,
} from "@/lib/generalScheduleImport";

const references = {
  eventStart: "2026-08-01",
  eventEnd: "2026-08-03",
  boundary: { offsetHour: 6 },
  types: [{ id: 1, event_id: 7, name: "Session" }],
  locations: [{ id: 2, event_id: 7, name: "Main Hall" }],
  views: [{ id: 3, event_id: 7, name: "Delegates" }],
  teams: [{ id: 4, event_id: 7, name: "Officials" }],
  existing: [],
};

describe("General Schedule spreadsheet import", () => {
  it("resolves event references and after-midnight working days", () => {
    const result = parseGeneralScheduleSpreadsheet(
      `${GENERAL_SCHEDULE_IMPORT_HEADER}\n2026-08-01\t01:00\t02:00\tNight session\tSession\tMain Hall\tDelegates\tOfficials\tBring a badge`,
      references,
    );

    expect(result.headerErrors).toEqual([]);
    expect(result.rows[0].errors).toEqual([]);
    expect(result.rows[0].payload).toMatchObject({
      title: "Night session",
      date: "2026-08-02",
      session_element_type_id: 1,
      location_id: 2,
      schedule_view_ids: [3],
      attendee_team_ids: [4],
    });
  });

  it("reports missing references and invalid times before import", () => {
    const result = parseGeneralScheduleSpreadsheet(
      `${GENERAL_SCHEDULE_IMPORT_HEADER}\n2026-08-01\t10:00\t09:00\tInvalid\tUnknown\tElsewhere\tMissing\tNobody\t`,
      references,
    );

    expect(result.rows[0].payload).toBeNull();
    expect(result.rows[0].errors).toEqual(expect.arrayContaining([
      "End must be after start.",
      'Type "Unknown" was not found in this event.',
      'Location "Elsewhere" was not found in this event.',
    ]));
  });

  it("marks exact existing and repeated rows as duplicates", () => {
    const source = `${GENERAL_SCHEDULE_IMPORT_HEADER}\n2026-08-01\t09:00\t10:00\tOpening\tSession\t\t\t\t\n2026-08-01\t09:00\t10:00\tOpening\tSession\t\t\t\t`;
    const existing = [{
      id: 8,
      event_id: 7,
      title: "Opening",
      date: "2026-08-01",
      start_time: "09:00",
      end_time: "10:00",
      attendee_team_ids: [],
      schedule_view_ids: [],
      visibility: "public" as const,
    }];

    const result = parseGeneralScheduleSpreadsheet(source, { ...references, existing });

    expect(result.rows.map((row) => row.duplicate)).toEqual([true, true]);
  });
});
