import React, { useState } from "react";
import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { CopiedTaskDateRepairModal } from "@/components/data/CopiedTaskDateRepairModal";
import type { CopiedTaskDateRepairPreview } from "@/lib/api";

const preview: CopiedTaskDateRepairPreview = {
  source_event_id: 1,
  target_event_id: 2,
  repairable_count: 1,
  candidates: [
    {
      task_instance_id: 42,
      name: "Opening task",
      current_date: "2026-08-01",
      proposed_date: "2026-09-10",
      proposed_day_index: 0,
      repairable: true,
      reason: null,
    },
    {
      task_instance_id: 43,
      name: "Out-of-range task",
      current_date: "2026-08-03",
      proposed_date: null,
      proposed_day_index: null,
      repairable: false,
      reason: "The target project is too short.",
    },
  ],
};

function ControlledRepairModal({ onConfirm }: { onConfirm: () => void }) {
  const [selectedIds, setSelectedIds] = useState([42]);
  return (
    <CopiedTaskDateRepairModal
      preview={preview}
      selectedTaskIds={selectedIds}
      onToggleTask={(taskId) =>
        setSelectedIds((current) =>
          current.includes(taskId)
            ? current.filter((id) => id !== taskId)
            : [...current, taskId],
        )
      }
      onCancel={() => {}}
      onConfirm={onConfirm}
    />
  );
}

describe("CopiedTaskDateRepairModal", () => {
  it("shows safe mappings and applies the selected task dates", async () => {
    const user = userEvent.setup();
    const onConfirm = vi.fn();
    render(<ControlledRepairModal onConfirm={onConfirm} />);

    expect(screen.getByText("Repair copied task dates")).toBeInTheDocument();
    expect(screen.getByText("Opening task")).toBeInTheDocument();
    expect(screen.getByRole("checkbox", { name: /Opening task/ })).toBeChecked();
    expect(
      screen.getByRole("checkbox", { name: /Out-of-range task/ }),
    ).toBeDisabled();
    expect(screen.getByText("The target project is too short.")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Repair 1 task date" }));
    expect(onConfirm).toHaveBeenCalledTimes(1);
  });

  it("disables repair when every safe candidate is deselected", async () => {
    const user = userEvent.setup();
    render(<ControlledRepairModal onConfirm={() => {}} />);

    await user.click(screen.getByRole("checkbox", { name: /Opening task/ }));
    expect(screen.getByRole("button", { name: "Repair 0 task dates" })).toBeDisabled();
  });
});
