/** Calm workspace heading and empty-state primitives. */
import React from "react";
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { EmptyState } from "@/components/ui/EmptyState";
import { PageHeader } from "@/components/ui/PageHeader";

describe("PageHeader", () => {
  it("renders workflow context, helper text and aligned actions", () => {
    render(
      <PageHeader
        eyebrow="Autumn Session"
        title="Task planning"
        description="Build and place operational tasks."
        actions={<button type="button">Create task</button>}
      />,
    );

    expect(screen.getByRole("heading", { name: "Task planning" })).toBeInTheDocument();
    expect(screen.getByText("Autumn Session")).toBeInTheDocument();
    expect(screen.getByText("Build and place operational tasks.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Create task" })).toBeInTheDocument();
  });
});

describe("EmptyState", () => {
  it("offers one clear next action without inventing placeholder data", () => {
    render(
      <EmptyState
        title="No locations yet"
        description="Add the places used by this event."
        action={<button type="button">Add location</button>}
      />,
    );

    expect(screen.getByRole("heading", { name: "No locations yet" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Add location" })).toBeInTheDocument();
  });
});
