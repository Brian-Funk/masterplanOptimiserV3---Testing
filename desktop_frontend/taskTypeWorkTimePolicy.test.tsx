import React from "react";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

const { getAll, update } = vi.hoisted(() => ({
  getAll: vi.fn(),
  update: vi.fn(),
}));

vi.mock("@/lib/api", () => ({
  taskTypesApi: {
    getAll,
    update,
    create: vi.fn(),
    delete: vi.fn(),
  },
}));

import { TaskTypesSection } from "@/app/dashboard/settings/components/TaskTypesSection";

describe("task-type working-time policy", () => {
  beforeEach(() => {
    getAll.mockReset();
    update.mockReset();
    getAll.mockResolvedValue([
      {
        id: 1,
        name: "Sleep",
        description: "Sleep in shifts",
        color: "#7986cb",
        sort_order: 1,
        is_active: true,
        fatigue_score: 0,
        counts_towards_work_time: false,
      },
    ]);
    update.mockResolvedValue({});
  });

  it("shows excluded task types and submits policy changes", async () => {
    render(<TaskTypesSection />);

    expect(await screen.findByText("Excluded")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Edit" }));

    const checkbox = screen.getByRole("checkbox", {
      name: /Count towards working-time limit/i,
    });
    expect(checkbox).not.toBeChecked();
    expect(
      screen.getByText(/Assigned people remain reserved/i),
    ).toBeInTheDocument();

    fireEvent.click(checkbox);
    fireEvent.click(screen.getByRole("button", { name: "Update" }));

    await waitFor(() =>
      expect(update).toHaveBeenCalledWith(
        1,
        expect.objectContaining({ counts_towards_work_time: true }),
      ),
    );
  });
});
