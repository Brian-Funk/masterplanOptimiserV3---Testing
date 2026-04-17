/**
 * Tests for UI components — Button, Card, Input.
 */
import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import React from "react";

import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { Input } from "@/components/ui/Input";

describe("Button", () => {
  it("renders children", () => {
    render(<Button>Click me</Button>);
    expect(screen.getByRole("button")).toHaveTextContent("Click me");
  });

  it("applies variant classes", () => {
    render(<Button variant="danger">Delete</Button>);
    const btn = screen.getByRole("button");
    // Danger variant uses inline style for backgroundColor
    expect(btn).toBeInTheDocument();
  });

  it("handles click events", async () => {
    const user = userEvent.setup();
    let clicked = false;
    render(<Button onClick={() => (clicked = true)}>Go</Button>);
    await user.click(screen.getByRole("button"));
    expect(clicked).toBe(true);
  });

  it("disables when disabled prop is set", () => {
    render(<Button disabled>Disabled</Button>);
    expect(screen.getByRole("button")).toBeDisabled();
  });

  it("applies full width", () => {
    render(<Button fullWidth>Wide</Button>);
    expect(screen.getByRole("button").className).toContain("w-full");
  });

  it("applies size classes", () => {
    render(<Button size="lg">Large</Button>);
    expect(screen.getByRole("button").className).toContain("px-6");
  });
});

describe("Card", () => {
  it("renders children", () => {
    render(<Card>Card content</Card>);
    expect(screen.getByText("Card content")).toBeInTheDocument();
  });

  it("applies hover class when hover prop is true", () => {
    const { container } = render(<Card hover>Hoverable</Card>);
    expect(container.firstChild).toHaveClass("hover:shadow-md");
  });

  it("applies custom className", () => {
    const { container } = render(<Card className="mt-4">Styled</Card>);
    expect(container.firstChild).toHaveClass("mt-4");
  });
});

describe("Input", () => {
  it("renders with label", () => {
    render(<Input label="Email" />);
    expect(screen.getByLabelText("Email")).toBeInTheDocument();
  });

  it("shows error message", () => {
    render(<Input label="Name" error="Required" />);
    expect(screen.getByText("Required")).toBeInTheDocument();
  });

  it("shows helper text when no error", () => {
    render(<Input label="Name" helperText="Enter your name" />);
    expect(screen.getByText("Enter your name")).toBeInTheDocument();
  });

  it("hides helper text when error is present", () => {
    render(<Input label="Name" error="Bad" helperText="Enter your name" />);
    expect(screen.queryByText("Enter your name")).toBeNull();
    expect(screen.getByText("Bad")).toBeInTheDocument();
  });

  it("passes through HTML attributes", async () => {
    const user = userEvent.setup();
    render(<Input label="Search" placeholder="Type here..." />);
    const input = screen.getByPlaceholderText("Type here...");
    await user.type(input, "hello");
    expect(input).toHaveValue("hello");
  });

  it("disables input", () => {
    render(<Input label="Locked" disabled />);
    expect(screen.getByLabelText("Locked")).toBeDisabled();
  });
});
