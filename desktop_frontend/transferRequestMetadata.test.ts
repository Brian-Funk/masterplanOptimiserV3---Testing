import { describe, expect, it, vi, beforeEach } from "vitest";

const { capabilitiesGetAll, flowCheck } = vi.hoisted(() => ({
  capabilitiesGetAll: vi.fn(),
  flowCheck: vi.fn(),
}));

vi.mock("@/lib/api", () => ({
  capabilitiesApi: {
    getAll: capabilitiesGetAll,
  },
  flowApi: {
    check: flowCheck,
  },
}));

import { performFlowCheck } from "@/app/dashboard/admin/tabs/cmi/flowCheckUtils";

describe("transfer request metadata", () => {
  beforeEach(() => {
    capabilitiesGetAll.mockReset();
    flowCheck.mockReset();
  });

  it("uses template transfer metadata when task instance flags are stale", async () => {
    capabilitiesGetAll.mockResolvedValue([]);
    flowCheck.mockResolvedValue({ feasible: true, errors: [] });

    await performFlowCheck({
      selectedEvent: { id: 1 },
      selectedDate: "2026-08-01",
      templates: [
        {
          id: 10,
          name: "Transfer",
          is_floating: false,
          is_transfer: true,
          fields: [
            { id: "field_start_location", name: "From", type: "start_location" },
            { id: "field_end_location", name: "To", type: "end_location" },
          ],
        } as any,
      ],
      persons: [
        {
          id: 1,
          first_name: "Elena",
          last_name: "Macura",
          global_data: {},
          home_location_id: 1,
        } as any,
      ],
      locations: [
        { id: 1, name: "Hotel" },
        { id: 2, name: "Venue" },
      ],
      taskInstances: [
        {
          id: 41,
          event_id: 1,
          template_id: 10,
          date: "2026-08-01",
          is_transfer: false,
          is_floating: false,
          field_values: {
            field_start_location: 1,
            field_end_location: 2,
          },
        },
      ],
      silent: true,
    });

    expect(flowCheck).toHaveBeenCalledTimes(1);
    const payload = flowCheck.mock.calls[0][0];
    expect(payload.tasks[0]).toEqual(
      expect.objectContaining({
        id: 41,
        location_id: 1,
        is_transfer: true,
        is_floating: false,
      }),
    );
  });
});
