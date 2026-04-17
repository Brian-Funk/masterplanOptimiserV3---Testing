/**
 * Tests for additional desktop UI components — Input, Select, Badge,
 * Spinner, Switch, Divider, IconButton, ToastContainer, DataTable.
 */
import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent, within } from "@testing-library/react";
import React from "react";

import { Input } from "@/components/ui/Input";
import { Select } from "@/components/ui/Select";
import { Badge } from "@/components/ui/Badge";
import { Spinner } from "@/components/ui/Spinner";
import { Switch } from "@/components/ui/Switch";
import { Divider } from "@/components/ui/Divider";
import { IconButton } from "@/components/ui/IconButton";

// ───────────────────── Input ─────────────────────

describe("Input", () => {
  it("renders with label", () => {
    render(<Input label="Email" />);
    expect(screen.getByLabelText("Email")).toBeInTheDocument();
  });

  it("renders without label", () => {
    const { container } = render(<Input placeholder="type here" />);
    expect(container.querySelector("label")).toBeNull();
    expect(screen.getByPlaceholderText("type here")).toBeInTheDocument();
  });

  it("shows error message and error styling", () => {
    render(<Input label="Name" error="Required" />);
    expect(screen.getByText("Required")).toBeInTheDocument();
    const input = screen.getByLabelText("Name");
    expect(input.className).toContain("border-red-300");
  });

  it("shows helper text when no error", () => {
    render(<Input helperText="Enter your email" />);
    expect(screen.getByText("Enter your email")).toBeInTheDocument();
  });

  it("hides helper text when error is present", () => {
    render(<Input helperText="Help" error="Error" />);
    expect(screen.queryByText("Help")).toBeNull();
    expect(screen.getByText("Error")).toBeInTheDocument();
  });

  it("uses provided id", () => {
    render(<Input id="my-input" label="Custom" />);
    expect(screen.getByLabelText("Custom")).toHaveAttribute("id", "my-input");
  });

  it("generates id when none provided", () => {
    render(<Input label="Auto" />);
    const input = screen.getByLabelText("Auto");
    expect(input.id).toMatch(/^input-/);
  });

  it("supports disabled state", () => {
    render(<Input label="Disabled" disabled />);
    expect(screen.getByLabelText("Disabled")).toBeDisabled();
  });

  it("merges custom className", () => {
    render(<Input className="extra" />);
    const input = screen.getByRole("textbox");
    expect(input.className).toContain("extra");
  });
});

// ───────────────────── Select ─────────────────────

describe("Select", () => {
  const options = [
    { value: "a", label: "Alpha" },
    { value: "b", label: "Beta" },
    { value: "c", label: "Charlie" },
  ];

  it("renders label and options", () => {
    render(<Select label="Picker" options={options} />);
    expect(screen.getByLabelText("Picker")).toBeInTheDocument();
    expect(screen.getByText("Alpha")).toBeInTheDocument();
    expect(screen.getByText("Beta")).toBeInTheDocument();
    expect(screen.getByText("Charlie")).toBeInTheDocument();
  });

  it("renders without label", () => {
    const { container } = render(<Select options={options} />);
    expect(container.querySelector("label")).toBeNull();
  });

  it("shows error message", () => {
    render(<Select options={options} error="Pick one" />);
    expect(screen.getByText("Pick one")).toBeInTheDocument();
  });

  it("applies error styling", () => {
    render(<Select label="Sel" options={options} error="Bad" />);
    const select = screen.getByLabelText("Sel");
    expect(select.className).toContain("border-red-300");
  });

  it("uses provided id", () => {
    render(<Select id="my-select" label="Sel" options={options} />);
    expect(screen.getByLabelText("Sel")).toHaveAttribute("id", "my-select");
  });

  it("generates id when none provided", () => {
    render(<Select label="Auto" options={options} />);
    expect(screen.getByLabelText("Auto").id).toMatch(/^select-/);
  });

  it("supports numeric option values", () => {
    const numOptions = [
      { value: 1, label: "One" },
      { value: 2, label: "Two" },
    ];
    render(<Select options={numOptions} />);
    expect(screen.getByText("One")).toBeInTheDocument();
    expect(screen.getByText("Two")).toBeInTheDocument();
  });

  it("supports disabled state", () => {
    render(<Select label="Dis" options={options} disabled />);
    expect(screen.getByLabelText("Dis")).toBeDisabled();
  });
});

// ───────────────────── Badge ─────────────────────

describe("Badge", () => {
  it("renders children text", () => {
    render(<Badge>Active</Badge>);
    expect(screen.getByText("Active")).toBeInTheDocument();
  });

  it("neutral variant uses default bg class", () => {
    const { container } = render(<Badge variant="neutral">N</Badge>);
    expect(container.firstChild).toHaveClass("bg-surface-inset");
  });

  it("non-neutral variants apply inline styles", () => {
    const { container } = render(<Badge variant="success">OK</Badge>);
    const span = container.firstChild as HTMLElement;
    expect(span.style.color).toBe("var(--color-success)");
  });

  it("merges custom className", () => {
    const { container } = render(<Badge className="ml-2">X</Badge>);
    expect(container.firstChild).toHaveClass("ml-2");
  });

  it("applies danger variant with error color", () => {
    const { container } = render(<Badge variant="danger">!</Badge>);
    const span = container.firstChild as HTMLElement;
    expect(span.style.color).toBe("var(--color-error)");
  });

  it("applies primary variant with primary color", () => {
    const { container } = render(<Badge variant="primary">P</Badge>);
    const span = container.firstChild as HTMLElement;
    expect(span.style.color).toBe("var(--color-primary)");
  });

  it("defaults to neutral variant", () => {
    const { container } = render(<Badge>Default</Badge>);
    expect(container.firstChild).toHaveClass("bg-surface-inset");
  });
});

// ───────────────────── Spinner ─────────────────────

describe("Spinner", () => {
  it("renders a div with animate-spin", () => {
    const { container } = render(<Spinner />);
    expect(container.firstChild).toHaveClass("animate-spin");
  });

  it("applies sm size class", () => {
    const { container } = render(<Spinner size="sm" />);
    expect(container.firstChild).toHaveClass("w-4", "h-4");
  });

  it("applies md size class (default)", () => {
    const { container } = render(<Spinner />);
    expect(container.firstChild).toHaveClass("w-8", "h-8");
  });

  it("applies lg size class", () => {
    const { container } = render(<Spinner size="lg" />);
    expect(container.firstChild).toHaveClass("w-12", "h-12");
  });

  it("merges custom className", () => {
    const { container } = render(<Spinner className="mt-4" />);
    expect(container.firstChild).toHaveClass("mt-4");
  });
});

// ───────────────────── Switch ─────────────────────

describe("Switch", () => {
  it("renders with role=switch", () => {
    render(<Switch checked={false} onChange={() => {}} />);
    expect(screen.getByRole("switch")).toBeInTheDocument();
  });

  it("reflects checked state via aria-checked", () => {
    const { rerender } = render(<Switch checked={false} onChange={() => {}} />);
    expect(screen.getByRole("switch")).toHaveAttribute("aria-checked", "false");

    rerender(<Switch checked={true} onChange={() => {}} />);
    expect(screen.getByRole("switch")).toHaveAttribute("aria-checked", "true");
  });

  it("calls onChange with toggled value", () => {
    const onChange = vi.fn();
    render(<Switch checked={false} onChange={onChange} />);
    fireEvent.click(screen.getByRole("switch"));
    expect(onChange).toHaveBeenCalledWith(true);
  });

  it("calls onChange with false when unchecking", () => {
    const onChange = vi.fn();
    render(<Switch checked={true} onChange={onChange} />);
    fireEvent.click(screen.getByRole("switch"));
    expect(onChange).toHaveBeenCalledWith(false);
  });

  it("renders left and right labels", () => {
    render(
      <Switch
        checked={false}
        onChange={() => {}}
        leftLabel="Off"
        rightLabel="On"
      />,
    );
    expect(screen.getByText("Off")).toBeInTheDocument();
    expect(screen.getByText("On")).toBeInTheDocument();
  });

  it("disables the switch", () => {
    render(<Switch checked={false} onChange={() => {}} disabled />);
    expect(screen.getByRole("switch")).toBeDisabled();
  });

  it("does not fire onChange when disabled", () => {
    const onChange = vi.fn();
    render(<Switch checked={false} onChange={onChange} disabled />);
    fireEvent.click(screen.getByRole("switch"));
    expect(onChange).not.toHaveBeenCalled();
  });
});

// ───────────────────── Divider ─────────────────────

describe("Divider", () => {
  it("renders an hr element", () => {
    const { container } = render(<Divider />);
    expect(container.querySelector("hr")).toBeInTheDocument();
  });

  it("merges custom className", () => {
    const { container } = render(<Divider className="my-4" />);
    expect(container.querySelector("hr")).toHaveClass("my-4");
  });
});

// ───────────────────── IconButton ─────────────────────

describe("IconButton", () => {
  it("renders a button with children", () => {
    render(<IconButton>X</IconButton>);
    expect(screen.getByRole("button")).toHaveTextContent("X");
  });

  it("applies ghost variant by default", () => {
    render(<IconButton>G</IconButton>);
    expect(screen.getByRole("button").className).toContain(
      "text-foreground-muted",
    );
  });

  it("applies primary variant inline style", () => {
    render(<IconButton variant="primary">P</IconButton>);
    const btn = screen.getByRole("button");
    expect(btn.style.backgroundColor).toBe("var(--color-primary)");
  });

  it("applies secondary variant inline style", () => {
    render(<IconButton variant="secondary">S</IconButton>);
    const btn = screen.getByRole("button");
    expect(btn.style.backgroundColor).toBe("var(--color-secondary)");
  });

  it("applies size classes", () => {
    const { rerender } = render(<IconButton size="sm">S</IconButton>);
    expect(screen.getByRole("button")).toHaveClass("w-8", "h-8");

    rerender(<IconButton size="md">M</IconButton>);
    expect(screen.getByRole("button")).toHaveClass("w-10", "h-10");

    rerender(<IconButton size="lg">L</IconButton>);
    expect(screen.getByRole("button")).toHaveClass("w-12", "h-12");
  });

  it("supports disabled state", () => {
    render(<IconButton disabled>D</IconButton>);
    expect(screen.getByRole("button")).toBeDisabled();
  });

  it("fires onClick", () => {
    const onClick = vi.fn();
    render(<IconButton onClick={onClick}>C</IconButton>);
    fireEvent.click(screen.getByRole("button"));
    expect(onClick).toHaveBeenCalledTimes(1);
  });
});
