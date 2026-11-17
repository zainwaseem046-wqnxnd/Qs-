import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Button } from "./button";
import { Field, Input } from "./form";
import { DataTable } from "./table";

describe("Field", () => {
  it("associates label, control and error for assistive technology", () => {
    render(<Field label="Project name" error="Required" required>{(p) => <Input {...p} />}</Field>);
    const input = screen.getByLabelText(/Project name/);
    expect(input).toHaveAttribute("aria-invalid", "true");
    expect(screen.getByRole("alert")).toHaveTextContent("Required");
    expect(input.getAttribute("aria-describedby")).toBe(screen.getByRole("alert").id);
  });
});

describe("Button", () => {
  it("is disabled and busy while loading", () => {
    render(<Button loading>Save</Button>);
    const btn = screen.getByRole("button", { name: "Save" });
    expect(btn).toBeDisabled();
    expect(btn).toHaveAttribute("aria-busy", "true");
  });
});

describe("DataTable", () => {
  it("renders rows and reports sort changes with aria-sort", async () => {
    const onSort = vi.fn();
    const rows = [{ id: "1", name: "Alpha" }, { id: "2", name: "Bravo" }];
    render(
      <DataTable
        caption="Test"
        rows={rows}
        rowKey={(r) => r.id}
        columns={[{ key: "name", header: "Name", sortable: true, cell: (r) => r.name }]}
        sort={{ key: "name", order: "asc" }}
        onSort={onSort}
      />,
    );
    expect(screen.getByRole("columnheader")).toHaveAttribute("aria-sort", "ascending");
    expect(screen.getAllByRole("row")).toHaveLength(3);
    await userEvent.click(screen.getByRole("button", { name: /Name/ }));
    expect(onSort).toHaveBeenCalledWith({ key: "name", order: "desc" });
  });
});
