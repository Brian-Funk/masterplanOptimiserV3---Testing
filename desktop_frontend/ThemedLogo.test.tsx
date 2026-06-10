import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import React from "react";

vi.mock("@/contexts/ThemeContext", () => ({
  useTheme: () => ({
    isDark: false,
    theme: {
      primary_color_1: "#ff0000",
      primary_color_2: "#00ff00",
    },
  }),
}));

import ThemedLogo from "@/components/ThemedLogo";

describe("ThemedLogo", () => {
  it("uses fixed brand colours instead of custom theme primary colours", () => {
    const { container } = render(<ThemedLogo />);

    const gradient = container.querySelector(".absolute.inset-0") as HTMLElement;
    expect(gradient.style.background).toContain("#2563eb");
    expect(gradient.style.background).toContain("#7c3aed");
    expect(gradient.style.background).not.toContain("#ff0000");
    expect(gradient.style.background).not.toContain("#00ff00");
    expect(screen.getByAltText("Logo")).toBeInTheDocument();
  });
});
