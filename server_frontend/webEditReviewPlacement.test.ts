import { describe, expect, it } from "vitest";
import fs from "node:fs";
import path from "node:path";
import { resolveServerRoot } from "../test_support/repoRoots";

const serverSrc = path.join(resolveServerRoot(), "web", "src");

function readSource(relativePath: string): string {
  return fs.readFileSync(path.join(serverSrc, relativePath), "utf8");
}

describe("web edit review placement", () => {
  it("does not mount the full review workflow on the broad admin page", () => {
    const adminPage = readSource(path.join("app", "admin", "page.tsx"));

    expect(adminPage).not.toContain("WebEditSummaryBar");
    expect(adminPage).not.toContain("<WebEditReviewModal");
  });

  it("mounts the review workflow from the schedule calendar context", () => {
    const calendarPage = readSource(path.join("app", "calendar", "page.tsx"));

    expect(calendarPage).toContain("ScheduleWebEditIndicator");
    expect(calendarPage).toContain("<WebEditReviewModal");
    expect(calendarPage).toContain("/web-edits");
  });
});
