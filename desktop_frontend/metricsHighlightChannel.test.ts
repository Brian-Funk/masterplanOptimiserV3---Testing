import { describe, expect, it, vi } from "vitest";
import {
  METRIC_HIGHLIGHT_CLEAR_MESSAGE,
  postMetricHighlightClear,
} from "@/lib/metricsHighlightChannel";

describe("metrics highlight channel", () => {
  it("posts the clear message used to remove temporary schedule highlights", () => {
    const channel = { postMessage: vi.fn() };

    postMetricHighlightClear(channel);

    expect(channel.postMessage).toHaveBeenCalledWith(
      METRIC_HIGHLIGHT_CLEAR_MESSAGE,
    );
  });

  it("ignores missing channels", () => {
    expect(() => postMetricHighlightClear(null)).not.toThrow();
  });
});
