import React from "react";
import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { ImportPreviewModal } from "@/components/import/ImportPreviewModal";
import type { ImportValidationResult } from "@/lib/api";
import {
  buildInvalidJsonImportValidation,
  formatImportContents,
  getImportActionLabel,
  getImportPreviewStatus,
  hasBlockingImportErrors,
} from "@/lib/importPreview";

type PreviewOverrides = Partial<Omit<ImportValidationResult, "summary">> & {
  summary?: Partial<ImportValidationResult["summary"]>;
};

function validPreview(overrides: PreviewOverrides = {}): ImportValidationResult {
  const base: ImportValidationResult = {
    isValid: true,
    errors: [],
    warnings: [],
    info: [
      {
        id: "version",
        severity: "info",
        title: "File version",
        message: "Export version 1.",
        path: "version",
      },
    ],
    summary: {
      projectName: "Conference",
      eventName: "Conference",
      dateRange: "01.08.2026 - 03.08.2026",
      sourceVersion: "1",
      exportedAt: "2026-05-20T10:00:00",
      peopleCount: 42,
      locationCount: 8,
      groupCount: 6,
      taskCount: 128,
      templateCount: 5,
      taskTypeCount: 4,
      assignmentCount: 96,
      hasOptimisedSchedule: true,
      hasFinalSchedule: true,
      hasPublishMetadata: true,
      hasAppSettings: true,
      importType: "project",
    },
  };
  return {
    ...base,
    ...overrides,
    summary: { ...base.summary, ...overrides.summary },
  };
}

describe("desktop import preview helpers", () => {
  it("builds a blocking validation result for invalid JSON", () => {
    const result = buildInvalidJsonImportValidation();

    expect(result.isValid).toBe(false);
    expect(result.errors[0].title).toBe("Invalid JSON");
    expect(hasBlockingImportErrors(result)).toBe(true);
    expect(getImportPreviewStatus(result).title).toBe("Cannot import");
  });

  it("formats the import contents summary with recognised entity counts", () => {
    expect(formatImportContents(validPreview().summary)).toBe(
      "42 people, 8 locations, 6 groups, 128 tasks, 5 templates, 96 assignments",
    );
  });

  it("uses application settings as the fallback import action", () => {
    const validation = validPreview({
      summary: {
        projectName: null,
        eventName: null,
        peopleCount: 0,
        locationCount: 0,
        groupCount: 0,
        taskCount: 0,
        templateCount: 0,
        taskTypeCount: 0,
        assignmentCount: 0,
        hasOptimisedSchedule: false,
        hasFinalSchedule: false,
        hasPublishMetadata: false,
        hasAppSettings: true,
        importType: "app_settings",
      },
    });

    expect(formatImportContents(validation.summary)).toBe(
      "application settings",
    );
    expect(getImportActionLabel(validation.summary)).toBe(
      "Import application settings",
    );
  });
});

describe("ImportPreviewModal", () => {
  it("renders counts, schedule metadata, and the new-project import action", () => {
    render(
      <ImportPreviewModal
        open
        fileName="backup.json"
        validation={validPreview()}
        onCancel={() => {}}
        onChooseAnother={() => {}}
        onConfirm={() => {}}
      />,
    );

    expect(screen.getByText("Import preview")).toBeInTheDocument();
    expect(screen.getAllByText("Conference")[0]).toBeInTheDocument();
    expect(screen.getByText("01.08.2026 - 03.08.2026")).toBeInTheDocument();
    expect(screen.getByText("128")).toBeInTheDocument();
    expect(
      screen.getByText("Optimised schedule: included"),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "Import as new project" }),
    ).toBeEnabled();
  });

  it("disables confirmation when blocking errors exist", () => {
    const validation = validPreview({
      isValid: false,
      errors: [
        {
          id: "missing_global_data",
          severity: "error",
          title: "Missing application settings",
          message: "The file is missing the required global_data section.",
          path: "global_data",
        },
      ],
    });

    render(
      <ImportPreviewModal
        open
        validation={validation}
        onCancel={() => {}}
        onConfirm={() => {}}
      />,
    );

    expect(screen.getByText("Cannot import")).toBeInTheDocument();
    expect(screen.getByText("Missing application settings")).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "Import as new project" }),
    ).toBeDisabled();
  });

  it("shows warnings without blocking the final import action", () => {
    const validation = validPreview({
      warnings: [
        {
          id: "no_people",
          severity: "warning",
          title: "No people included",
          message: "This project has no people in the import.",
          path: "events[0].persons",
        },
      ],
    });

    render(
      <ImportPreviewModal
        open
        validation={validation}
        onCancel={() => {}}
        onConfirm={() => {}}
      />,
    );

    expect(screen.getByText("Review recommended")).toBeInTheDocument();
    expect(screen.getByText("No people included")).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "Import as new project" }),
    ).toBeEnabled();
  });

  it("calls confirm, cancel, and choose-another handlers", async () => {
    const user = userEvent.setup();
    const onConfirm = vi.fn();
    const onCancel = vi.fn();
    const onChooseAnother = vi.fn();

    render(
      <ImportPreviewModal
        open
        validation={validPreview()}
        onCancel={onCancel}
        onChooseAnother={onChooseAnother}
        onConfirm={onConfirm}
      />,
    );

    await user.click(
      screen.getByRole("button", { name: "Import as new project" }),
    );
    await user.click(screen.getByRole("button", { name: "Choose another file" }));
    await user.click(screen.getByRole("button", { name: "Cancel" }));

    expect(onConfirm).toHaveBeenCalledTimes(1);
    expect(onChooseAnother).toHaveBeenCalledTimes(1);
    expect(onCancel).toHaveBeenCalledTimes(1);
  });
});
