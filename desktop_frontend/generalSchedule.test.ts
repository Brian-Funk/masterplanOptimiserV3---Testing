import { describe, expect, it } from "vitest";
import {
  buildGeneralSchedulePublicFingerprintSource,
  renderSessionElementTemplateHtml,
  renderSessionElementTemplateText,
  renderSessionElementsTemplateHtml,
  renderSessionElementsTemplateText,
  sanitizeGeneralScheduleHtml,
} from "@/lib/generalSchedule";
import {
  getActualDateForWorkingSlot,
  getScheduleDayBoundaryFromRange,
  getWorkingDayEndDateTimeLimit,
  getWorkingDayForDateTime,
} from "@/lib/workingDayBoundary";

const teams = [
  { id: 1, event_id: 10, name: "FEMM", category_id: 2 },
  { id: 2, event_id: 10, name: "Officials", category_id: 1 },
];

const scheduleViews = [
  { id: 4, event_id: 10, name: "Delegates", sort_order: 0 },
];

const locations = [
  { id: 7, event_id: 10, name: "Room A", address: "", capacity: null },
];

const persons = [
  { id: 3, first_name: "Anna", last_name: "Muller" },
];

const types = [
  {
    id: 5,
    event_id: 10,
    name: "Committee session",
    colour: "#a5b4fc",
    copy_template_html:
      "<b>{title}</b><br>{date} {start_time}-{end_time}<br><i>{location}</i><br>{audience_teams}<br>{responsible}",
  },
];

const element = {
  id: 11,
  event_id: 10,
  session_element_type_id: 5,
  title: "Opening Briefing",
  date: "2026-06-21",
  start_time: "09:00",
  end_time: "10:00",
  location_id: 7,
  responsible_person_id: 3,
  responsible_text: "",
  attendee_team_ids: [1],
  schedule_view_ids: [4],
  visibility: "public" as const,
  description: "Bring laptops.",
  sort_order: 0,
};

describe("general schedule templates", () => {
  it("renders rich type templates with resolved variables", () => {
    expect(
      renderSessionElementTemplateHtml(element, teams, locations, persons, types),
    ).toContain("<b>Opening Briefing</b>");
    expect(
      renderSessionElementTemplateHtml(element, teams, locations, persons, types),
    ).toContain("<i>Room A</i>");
    expect(
      renderSessionElementTemplateText(element, teams, locations, persons, types),
    ).toContain("Anna Muller");
  });

  it("sanitizes generated rich HTML to the allowed formatting subset", () => {
    const sanitized = sanitizeGeneralScheduleHtml(
      '<b>Safe</b><script>alert(1)</script><a href="javascript:alert(1)">bad</a><u>ok</u>',
    );

    expect(sanitized).toContain("<b>Safe</b>");
    expect(sanitized).toContain("<u>ok</u>");
    expect(sanitized).not.toContain("<script>");
    expect(sanitized).not.toContain("javascript:");
  });

  it("builds public fingerprints from public elements and their type metadata only", () => {
    const internalElement = {
      ...element,
      id: 12,
      title: "Internal prep",
      visibility: "internal" as const,
    };
    const source = JSON.parse(buildGeneralSchedulePublicFingerprintSource(
      [element, internalElement],
      teams,
      locations,
      persons,
      types,
      scheduleViews,
    ));

    expect(source).toHaveLength(1);
    expect(source[0]).toMatchObject({
      id: 11,
      type_id: 5,
      colour: "#a5b4fc",
      copy_template_html: types[0].copy_template_html,
      location_name: "Room A",
    });
    expect(source[0].schedule_views).toEqual([
      expect.objectContaining({ id: 4, name: "Delegates" }),
    ]);
    expect(source[0].audience_teams).toEqual([
      expect.objectContaining({ id: 1, name: "FEMM" }),
    ]);
  });

  it("excludes public elements without a selected schedule view from public fingerprints", () => {
    const noViewElement = {
      ...element,
      id: 13,
      title: "No public view",
      schedule_view_ids: [],
    };
    const source = JSON.parse(buildGeneralSchedulePublicFingerprintSource(
      [element, noViewElement],
      teams,
      locations,
      persons,
      types,
      scheduleViews,
    ));

    expect(source).toHaveLength(1);
    expect(source[0].title).toBe("Opening Briefing");
  });

  it("renders copied elements as separate text and HTML lines", () => {
    const secondElement = {
      ...element,
      id: 12,
      title: "Jury Briefing",
      start_time: "10:30",
      end_time: "11:00",
    };

    expect(
      renderSessionElementsTemplateText(
        [element, secondElement],
        teams,
        locations,
        persons,
        types,
      ),
    ).toContain("Anna Muller\nJury Briefing");
    expect(
      renderSessionElementsTemplateHtml(
        [element, secondElement],
        teams,
        locations,
        persons,
        types,
      ),
    ).toContain("Anna Muller<br><b>Jury Briefing</b>");
  });
});

describe("general schedule working-day dates", () => {
  it("uses the schedule display range cutoff when grouping after-midnight elements", () => {
    const boundary = getScheduleDayBoundaryFromRange({
      startHour: 6,
      endHour: 28,
    });

    expect(getWorkingDayForDateTime("2026-06-22", "01:00", boundary)).toBe(
      "2026-06-21",
    );
    expect(getWorkingDayForDateTime("2026-06-22", "04:00", boundary)).toBe(
      "2026-06-22",
    );
  });

  it("stores after-midnight General Schedule entries on the real next date", () => {
    const boundary = getScheduleDayBoundaryFromRange({
      startHour: 6,
      endHour: 28,
    });

    expect(getActualDateForWorkingSlot("2026-06-21", "01:00", boundary)).toBe(
      "2026-06-22",
    );
    expect(getActualDateForWorkingSlot("2026-06-21", "04:00", boundary)).toBe(
      "2026-06-21",
    );
  });

  it("extends final-day availability input to the configured overnight tail", () => {
    const boundary = getScheduleDayBoundaryFromRange({
      startHour: 6,
      endHour: 28,
    });

    expect(getWorkingDayEndDateTimeLimit("2026-06-21", boundary)).toBe(
      "2026-06-22T04:00",
    );
    expect(getWorkingDayEndDateTimeLimit("2026-06-21", { offsetHour: 0 })).toBe(
      "2026-06-21T23:59",
    );
  });
});
