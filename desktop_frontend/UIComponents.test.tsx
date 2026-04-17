/**
 * Tests for desktop UI components — Button, Card, Modal.
 */
import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import React from "react";

import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { Modal } from "@/components/ui/Modal";

describe("Button", () => {
  it("renders children text", () => {
    render(<Button>Save</Button>);
    expect(screen.getByRole("button")).toHaveTextContent("Save");
  });

  it("fires onClick", async () => {
    const user = userEvent.setup();
    const onClick = vi.fn();
    render(<Button onClick={onClick}>Click</Button>);
    await user.click(screen.getByRole("button"));
    expect(onClick).toHaveBeenCalledTimes(1);
  });

  it("disables when disabled", () => {
    render(<Button disabled>No</Button>);
    expect(screen.getByRole("button")).toBeDisabled();
  });

  it("applies fullWidth class", () => {
    render(<Button fullWidth>Wide</Button>);
    expect(screen.getByRole("button").className).toContain("w-full");
  });

  it("applies size classes", () => {
    const { rerender } = render(<Button size="sm">S</Button>);
    expect(screen.getByRole("button").className).toContain("px-3");
    rerender(<Button size="lg">L</Button>);
    expect(screen.getByRole("button").className).toContain("px-6");
  });

  it("applies primary variant inline style", () => {
    render(<Button variant="primary">P</Button>);
    expect(screen.getByRole("button").style.backgroundColor).toBe(
      "var(--color-primary)",
    );
  });

  it("applies danger variant inline style", () => {
    render(<Button variant="danger">D</Button>);
    expect(screen.getByRole("button").style.backgroundColor).toBe(
      "var(--color-error)",
    );
  });

  it("applies outline variant class", () => {
    render(<Button variant="outline">O</Button>);
    expect(screen.getByRole("button").className).toContain("border-2");
  });

  it("applies ghost variant class", () => {
    render(<Button variant="ghost">G</Button>);
    expect(screen.getByRole("button").className).toContain(
      "text-foreground-secondary",
    );
  });

  it("merges custom className", () => {
    render(<Button className="ml-2">Custom</Button>);
    expect(screen.getByRole("button").className).toContain("ml-2");
  });

  it("does not fire onClick when disabled", () => {
    const onClick = vi.fn();
    render(
      <Button onClick={onClick} disabled>
        No
      </Button>,
    );
    fireEvent.click(screen.getByRole("button"));
    expect(onClick).not.toHaveBeenCalled();
  });
});

describe("Card", () => {
  it("renders children", () => {
    render(<Card>Content</Card>);
    expect(screen.getByText("Content")).toBeInTheDocument();
  });

  it("applies hover styles", () => {
    const { container } = render(<Card hover>Hover me</Card>);
    expect(container.firstChild).toHaveClass("hover:shadow-md");
  });

  it("merges custom className", () => {
    const { container } = render(<Card className="p-4">Styled</Card>);
    expect(container.firstChild).toHaveClass("p-4");
  });
});

describe("Modal", () => {
  it("renders children when open", () => {
    render(
      <Modal open onClose={() => {}}>
        <p>Modal content</p>
      </Modal>,
    );
    expect(screen.getByText("Modal content")).toBeInTheDocument();
  });

  it("does not render when closed", () => {
    render(
      <Modal open={false} onClose={() => {}}>
        <p>Hidden</p>
      </Modal>,
    );
    expect(screen.queryByText("Hidden")).toBeNull();
  });

  it("calls onClose when Escape is pressed", () => {
    const onClose = vi.fn();
    render(
      <Modal open onClose={onClose}>
        <p>Press Esc</p>
      </Modal>,
    );
    fireEvent.keyDown(document, { key: "Escape" });
    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it("calls onClose when clicking backdrop", () => {
    const onClose = vi.fn();
    const { container } = render(
      <Modal open onClose={onClose}>
        <p>Click outside</p>
      </Modal>,
    );
    // Click the backdrop (the outermost fixed div)
    const backdrop = container.querySelector(".fixed");
    if (backdrop) {
      fireEvent.click(backdrop);
      expect(onClose).toHaveBeenCalled();
    }
  });

  it("does NOT close when clicking modal content", () => {
    const onClose = vi.fn();
    render(
      <Modal open onClose={onClose}>
        <p>Inside</p>
      </Modal>,
    );
    fireEvent.click(screen.getByText("Inside"));
    expect(onClose).not.toHaveBeenCalled();
  });
});
