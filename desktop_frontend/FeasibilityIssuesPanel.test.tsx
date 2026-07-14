import React from "react";
import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { FeasibilityIssuesPanel } from "@/components/FeasibilityIssuesPanel";
import type { FeasibilityDiagnostics } from "@/types/optimization";

const diagnostics: FeasibilityDiagnostics = {
  schema_version: 1,
  status: "infeasible",
  checked_scope: "full",
  summary: "No feasible schedule was found. Review 1 concrete requirement.",
  issues: [
    {
      code: "CAPABILITY_SHORTAGE",
      category: "capability",
      severity: "error",
      message: "First aid needs two nurses, but only one is eligible.",
      task_ids: [42],
      person_ids: [],
      transfer_ids: [],
      location_ids: [3],
      capability_ids: ["nurse"],
      facts: [
        { label: "Required", value: "2" },
        { label: "Eligible", value: "1" },
      ],
      suggestions: ["Add a qualified person or reduce the requirement."],
    },
  ],
};

describe("FeasibilityIssuesPanel", () => {
  it("shows a summary and expandable concrete evidence", () => {
    render(<FeasibilityIssuesPanel diagnostics={diagnostics} />);

    expect(screen.getByText(diagnostics.summary)).toBeInTheDocument();
    fireEvent.click(screen.getByText(diagnostics.issues[0].message));
    expect(screen.getByText("Required")).toBeInTheDocument();
    expect(screen.getByText("Eligible")).toBeInTheDocument();
    expect(
      screen.getByText("Add a qualified person or reduce the requirement."),
    ).toBeInTheDocument();
  });

  it("renders nothing for a feasible result without issues", () => {
    const { container } = render(
      <FeasibilityIssuesPanel
        diagnostics={{ ...diagnostics, status: "feasible", issues: [] }}
      />,
    );
    expect(container).toBeEmptyDOMElement();
  });
});
