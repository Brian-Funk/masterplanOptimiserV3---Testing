import React from "react";
import { fireEvent, render } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { RichTemplateEditor } from "@/components/RichTemplateEditor";

const variables = [
  { name: "title", label: "Title" },
  { name: "location", label: "Location" },
];

describe("RichTemplateEditor", () => {
  it("renders variables inside bold text as visibly formatted tokens", () => {
    const { container } = render(
      <RichTemplateEditor
        value="<b>{title}</b> <i>{location}</i>"
        onChange={() => {}}
        variables={variables}
      />,
    );

    const titleToken = container.querySelector(".variable-token");
    const editor = container.querySelector('[contenteditable="true"]');

    expect(titleToken?.closest("b")).not.toBeNull();
    expect(editor?.className).toContain("[&_b_.variable-token]:font-bold");
    expect(editor?.className).toContain("[&_i_.variable-token]:italic");
  });

  it("preserves inline formatting that the browser applies directly to variable tokens", () => {
    const onChange = vi.fn();
    const { container } = render(
      <RichTemplateEditor value="{title}" onChange={onChange} variables={variables} />,
    );
    const editor = container.querySelector('[contenteditable="true"]') as HTMLElement;

    editor.innerHTML =
      '<span style="font-weight: bold;"><span class="variable-token" contenteditable="false">{title}</span></span>';
    fireEvent.input(editor);

    expect(onChange).toHaveBeenLastCalledWith("<b>{title}</b>");
  });
});
