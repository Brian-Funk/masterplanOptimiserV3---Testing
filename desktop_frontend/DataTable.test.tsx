/**
 * Tests for DataTable — generic table component.
 */
import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import React from "react";
import { DataTable } from "@/components/DataTable";
import type { DataTableColumn } from "@/components/DataTable";

interface Row {
  id: number;
  name: string;
  age: number;
}

const columns: DataTableColumn<Row>[] = [
  { header: "Name", accessor: "name", enableDoubleClick: true },
  { header: "Age", accessor: "age" },
];

const data: Row[] = [
  { id: 1, name: "Alice", age: 30 },
  { id: 2, name: "Bob", age: 25 },
  { id: 3, name: "Charlie", age: 35 },
];

describe("DataTable", () => {
  it("renders column headers", () => {
    render(
      <DataTable columns={columns} data={data} keyExtractor={(r) => r.id} />,
    );
    expect(screen.getByText("Name")).toBeInTheDocument();
    expect(screen.getByText("Age")).toBeInTheDocument();
  });

  it("renders data rows", () => {
    render(
      <DataTable columns={columns} data={data} keyExtractor={(r) => r.id} />,
    );
    expect(screen.getByText("Alice")).toBeInTheDocument();
    expect(screen.getByText("Bob")).toBeInTheDocument();
    expect(screen.getByText("Charlie")).toBeInTheDocument();
    expect(screen.getByText("30")).toBeInTheDocument();
  });

  it("shows empty message when data is empty", () => {
    render(
      <DataTable
        columns={columns}
        data={[]}
        keyExtractor={(r) => r.id}
        emptyMessage="Nothing here"
      />,
    );
    expect(screen.getByText("Nothing here")).toBeInTheDocument();
  });

  it("shows default empty message", () => {
    render(
      <DataTable columns={columns} data={[]} keyExtractor={(r) => r.id} />,
    );
    expect(screen.getByText("No data available")).toBeInTheDocument();
  });

  it("shows empty sub-message", () => {
    render(
      <DataTable
        columns={columns}
        data={[]}
        keyExtractor={(r) => r.id}
        emptyMessage="Empty"
        emptySubMessage="Add some data"
      />,
    );
    expect(screen.getByText("Add some data")).toBeInTheDocument();
  });

  it("shows spinner when loading", () => {
    const { container } = render(
      <DataTable
        columns={columns}
        data={data}
        keyExtractor={(r) => r.id}
        isLoading
      />,
    );
    // Spinner has animate-spin class
    expect(container.querySelector(".animate-spin")).toBeInTheDocument();
    // Should not render table rows when loading
    expect(screen.queryByText("Alice")).toBeNull();
  });

  it("fires onRowDoubleClick for double-click-enabled columns", () => {
    const onDouble = vi.fn();
    render(
      <DataTable
        columns={columns}
        data={data}
        keyExtractor={(r) => r.id}
        onRowDoubleClick={onDouble}
      />,
    );
    // Double-click on the Name cell (enableDoubleClick=true)
    fireEvent.doubleClick(screen.getByText("Alice"));
    expect(onDouble).toHaveBeenCalledWith(data[0]);
  });

  it("does not fire onRowDoubleClick for non-enabled columns", () => {
    const onDouble = vi.fn();
    render(
      <DataTable
        columns={columns}
        data={data}
        keyExtractor={(r) => r.id}
        onRowDoubleClick={onDouble}
      />,
    );
    // Double-click on the Age cell (enableDoubleClick is not set)
    fireEvent.doubleClick(screen.getByText("30"));
    expect(onDouble).not.toHaveBeenCalled();
  });

  it("shows 'Double-click to edit' title on enabled cells", () => {
    render(
      <DataTable
        columns={columns}
        data={data}
        keyExtractor={(r) => r.id}
        onRowDoubleClick={() => {}}
      />,
    );
    const aliceCell = screen.getByText("Alice").closest("td");
    expect(aliceCell).toHaveAttribute("title", "Double-click to edit");

    const ageCell = screen.getByText("30").closest("td");
    expect(ageCell).not.toHaveAttribute("title");
  });

  it("uses custom render function", () => {
    const customColumns: DataTableColumn<Row>[] = [
      {
        header: "Info",
        render: (row) => (
          <span>
            {row.name} ({row.age})
          </span>
        ),
      },
    ];
    render(
      <DataTable
        columns={customColumns}
        data={data}
        keyExtractor={(r) => r.id}
      />,
    );
    expect(screen.getByText("Alice (30)")).toBeInTheDocument();
  });

  it("uses string keyExtractor", () => {
    const { container } = render(
      <DataTable
        columns={columns}
        data={data}
        keyExtractor={(r) => `row-${r.id}`}
      />,
    );
    const rows = container.querySelectorAll("tbody tr");
    expect(rows).toHaveLength(3);
  });
});
