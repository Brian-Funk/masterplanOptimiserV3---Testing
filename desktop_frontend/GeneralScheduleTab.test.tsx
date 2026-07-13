import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import React from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { GeneralScheduleTab } from "@/app/dashboard/admin/tabs/GeneralScheduleTab";
import { buildGeneralSchedulePublicFingerprint } from "@/lib/generalSchedule";

const mocks = vi.hoisted(() => ({
  getSessionElementTypes: vi.fn(),
  getTeams: vi.fn(),
  getScheduleViews: vi.fn(),
  getElements: vi.fn(),
  getPublishState: vi.fn(),
  getLocations: vi.fn(),
  getPersons: vi.fn(),
  getSettings: vi.fn(),
  publishGeneralSchedule: vi.fn(),
  bulkUpdateElements: vi.fn(),
  addToast: vi.fn(),
}));

vi.mock("@/contexts/ToastContext", () => ({
  useToast: () => ({ addToast: mocks.addToast }),
}));

vi.mock("@/lib/api", () => ({
  generalScheduleApi: {
    getSessionElementTypes: mocks.getSessionElementTypes,
    getTeams: mocks.getTeams,
    getScheduleViews: mocks.getScheduleViews,
    getElements: mocks.getElements,
    getPublishState: mocks.getPublishState,
    createElement: vi.fn(),
    updateElement: vi.fn(),
    deleteElement: vi.fn(),
    duplicateElement: vi.fn(),
    copyElements: vi.fn(),
    bulkUpdateElements: mocks.bulkUpdateElements,
  },
  locationsApi: { getAll: mocks.getLocations },
  personsApi: { getAll: mocks.getPersons },
  mpBackendApi: {
    getSettings: mocks.getSettings,
    publishGeneralSchedule: mocks.publishGeneralSchedule,
  },
}));

const selectedEvent = {
  id: 7,
  name: "Public Programme",
  start_date: "2026-08-01",
  end_date: "2026-08-02",
  meta_data: {},
};

const publicElement = {
  id: 10,
  event_id: 7,
  title: "Opening",
  date: "2026-08-01",
  start_time: "09:00",
  end_time: "10:00",
  session_element_type_id: 1,
  location_id: null,
  responsible_person_id: null,
  responsible_text: null,
  attendee_team_ids: [],
  schedule_view_ids: [20],
  visibility: "public" as const,
  description: null,
  sort_order: 0,
};

describe("GeneralScheduleTab publishing", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mocks.getSessionElementTypes.mockResolvedValue([
      { id: 1, name: "Session", colour: "#7dd3fc", sort_order: 0 },
    ]);
    mocks.getTeams.mockResolvedValue([]);
    mocks.getScheduleViews.mockResolvedValue([
      { id: 20, name: "Public", sort_order: 0 },
    ]);
    mocks.getElements.mockResolvedValue([
      publicElement,
      {
        ...publicElement,
        id: 11,
        title: "Internal draft",
        date: "2026-08-02",
        schedule_view_ids: [],
      },
    ]);
    mocks.getLocations.mockResolvedValue([]);
    mocks.getPersons.mockResolvedValue([]);
    mocks.getSettings.mockResolvedValue({ configured: true });
    mocks.getPublishState.mockResolvedValue({
      event_id: 7,
      item_count: 0,
      day_records: {
        "2026-08-01": {
          fingerprint: null,
          published_at: null,
          publish_failed_at: "2026-07-12T12:56:26Z",
          failure_message: "MP-Backend server is not configured.",
          item_count: 0,
        },
      },
    });
    mocks.publishGeneralSchedule.mockResolvedValue({
      status: "ok",
      items_published: 1,
    });
  });

  it("allows retrying a selected day after a previous failure", async () => {
    const user = userEvent.setup();
    render(<GeneralScheduleTab selectedEvent={selectedEvent} />);

    expect(await screen.findByText("Previous publish failed")).toBeInTheDocument();
    const publishButton = screen.getByRole("button", { name: "Publish" });
    expect(publishButton).toBeEnabled();
    await user.click(publishButton);
    await user.click(screen.getByRole("button", { name: "Publish selected day" }));

    await waitFor(() =>
      expect(mocks.publishGeneralSchedule).toHaveBeenCalledWith(7, ["2026-08-01"]),
    );
  });

  it("offers one full publish for all event days", async () => {
    const user = userEvent.setup();
    render(<GeneralScheduleTab selectedEvent={selectedEvent} />);

    await user.click(
      await screen.findByRole("button", { name: "More publish options" }),
    );
    await user.click(screen.getByRole("button", { name: "Publish all days" }));
    expect(await screen.findByText("Publish all 2 working days.")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Publish all days" }));

    await waitFor(() =>
      expect(mocks.publishGeneralSchedule).toHaveBeenCalledWith(7, undefined),
    );
  });

  it("keeps the publish action green when changes are pending", async () => {
    mocks.getPublishState.mockResolvedValue({
      event_id: 7,
      item_count: 1,
      day_records: {
        "2026-08-01": {
          fingerprint: "previous-fingerprint",
          published_at: "2026-07-13T10:00:00Z",
          publish_failed_at: null,
          failure_message: null,
          item_count: 1,
        },
      },
    });

    render(<GeneralScheduleTab selectedEvent={selectedEvent} />);

    expect(await screen.findByText("Changes pending")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Publish" })).toHaveClass(
      "bg-green-600",
    );
  });

  it("shows an unchanged published day as up to date", async () => {
    const fingerprint = await buildGeneralSchedulePublicFingerprint(
      [publicElement],
      [],
      [],
      [],
      [
        {
          id: 1,
          event_id: 7,
          name: "Session",
          colour: "#7dd3fc",
          sort_order: 0,
        },
      ],
      [{ id: 20, event_id: 7, name: "Public", sort_order: 0 }],
    );
    mocks.getPublishState.mockResolvedValue({
      event_id: 7,
      item_count: 1,
      day_records: {
        "2026-08-01": {
          fingerprint,
          published_at: "2026-07-13T10:00:00Z",
          publish_failed_at: null,
          failure_message: null,
          item_count: 1,
        },
      },
    });

    render(<GeneralScheduleTab selectedEvent={selectedEvent} />);

    expect(await screen.findByText("Up to date")).toBeInTheDocument();
    expect(screen.queryByText("Changes pending")).not.toBeInTheDocument();
  });
});
