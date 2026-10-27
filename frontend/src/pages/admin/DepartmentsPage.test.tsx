import { fireEvent, render, screen, within } from "@testing-library/react";
import { AxiosError, type AxiosResponse } from "axios";
import { vi } from "vitest";

import * as departmentService from "../../services/departmentService";
import type { AdminCategory, Department } from "../../types/department";
import DepartmentsPage from "./DepartmentsPage";

vi.mock("../../services/departmentService");

const ROADS: Department = {
  id: 1, name: "Roads Department", description: null, contact_email: null, is_active: true,
  created_at: "2026-10-01T00:00:00Z", updated_at: "2026-10-01T00:00:00Z",
};
const OLD: Department = { ...ROADS, id: 2, name: "Old Department", is_active: false };
const POTHOLES: AdminCategory = {
  id: 9, name: "Potholes", slug: "potholes", description: null, is_active: true, department: { id: 1, name: "Roads Department" },
  created_at: "2026-10-01T00:00:00Z", updated_at: "2026-10-01T00:00:00Z",
};

function apiError(status: number, detail: string) {
  return new AxiosError("failed", String(status), undefined, undefined, { status, data: { detail } } as AxiosResponse);
}

async function renderPage(departments: Department[] = [ROADS, OLD]) {
  vi.mocked(departmentService.listDepartments).mockResolvedValue(departments);
  vi.mocked(departmentService.listAdminCategories).mockResolvedValue([POTHOLES]);
  render(<DepartmentsPage />);
  await screen.findByText("Potholes");
}

afterEach(() => vi.resetAllMocks());

test("lists departments and categories with their mapping and status", async () => {
  await renderPage();
  expect(screen.getAllByText("Roads Department").length).toBeGreaterThanOrEqual(2); // department row + mapping
  expect(screen.getByText("Old Department")).toBeInTheDocument();
  expect(screen.getByText("Inactive")).toBeInTheDocument();
});

test("department form validates before calling the API", async () => {
  await renderPage();
  fireEvent.click(screen.getByRole("button", { name: "New department" }));
  const form = screen.getByRole("form", { name: "Department form" });

  fireEvent.change(within(form).getByLabelText("Department name"), { target: { value: " x " } });
  fireEvent.change(within(form).getByLabelText("Contact email (optional)"), { target: { value: "not-an-email" } });
  fireEvent.click(within(form).getByRole("button", { name: "Create department" }));

  expect(await screen.findByText("Name must be at least 2 characters.")).toBeInTheDocument();
  expect(screen.getByText("Enter a valid email address.")).toBeInTheDocument();
  expect(departmentService.createDepartment).not.toHaveBeenCalled();
});

test("creates a department and shows server conflicts", async () => {
  await renderPage();
  vi.mocked(departmentService.createDepartment).mockRejectedValueOnce(apiError(409, "A department named 'Water Board' already exists."));
  fireEvent.click(screen.getByRole("button", { name: "New department" }));
  const form = screen.getByRole("form", { name: "Department form" });
  fireEvent.change(within(form).getByLabelText("Department name"), { target: { value: "Water Board" } });
  fireEvent.click(within(form).getByRole("button", { name: "Create department" }));

  expect(await screen.findByText("A department named 'Water Board' already exists.")).toBeInTheDocument();
  expect(departmentService.createDepartment).toHaveBeenCalledWith({ name: "Water Board", description: null, contact_email: null });

  vi.mocked(departmentService.createDepartment).mockResolvedValueOnce({ ...ROADS, id: 3, name: "Water Works" });
  fireEvent.change(within(form).getByLabelText("Department name"), { target: { value: "Water Works" } });
  fireEvent.click(within(form).getByRole("button", { name: "Create department" }));
  expect(await screen.findByText("Water Works created.")).toBeInTheDocument();
});

test("category form requires a department and a valid slug; inactive departments cannot be chosen", async () => {
  await renderPage();
  fireEvent.click(screen.getByRole("button", { name: "New category" }));
  const form = screen.getByRole("form", { name: "Category form" });

  const department = within(form).getByLabelText("Routed to department");
  expect(within(department).getByRole("option", { name: "Old Department (inactive)" })).toBeDisabled();

  // The slug is suggested from the name.
  fireEvent.change(within(form).getByLabelText("Category name"), { target: { value: "Street Lights & Poles" } });
  expect(within(form).getByLabelText("Slug")).toHaveValue("street-lights-poles");

  fireEvent.change(within(form).getByLabelText("Slug"), { target: { value: "Bad slug!" } });
  fireEvent.click(within(form).getByRole("button", { name: "Create category" }));
  expect(await screen.findByText("Choose the department that handles this category.")).toBeInTheDocument();
  expect(screen.getByText(/Use lowercase letters, digits and single hyphens/)).toBeInTheDocument();
  expect(departmentService.createCategory).not.toHaveBeenCalled();

  vi.mocked(departmentService.createCategory).mockResolvedValue({ ...POTHOLES, id: 10, name: "Street Lights & Poles", slug: "street-lights" });
  fireEvent.change(within(form).getByLabelText("Slug"), { target: { value: "street-lights" } });
  fireEvent.change(department, { target: { value: "1" } });
  fireEvent.click(within(form).getByRole("button", { name: "Create category" }));

  expect(await screen.findByText("Street Lights & Poles created.")).toBeInTheDocument();
  expect(departmentService.createCategory).toHaveBeenCalledWith({
    name: "Street Lights & Poles", slug: "street-lights", description: null, department_id: 1,
  });
});

test("changing a category's department warns that only future complaints are affected", async () => {
  await renderPage([ROADS, OLD, { ...ROADS, id: 4, name: "GHMC Maintenance" }]);
  fireEvent.click(screen.getByRole("button", { name: "Edit Potholes" }));
  const form = screen.getByRole("form", { name: "Category form" });
  expect(screen.queryByText(/Only complaints filed after this change/)).not.toBeInTheDocument();

  vi.mocked(departmentService.updateCategory).mockResolvedValue({ ...POTHOLES, department: { id: 4, name: "GHMC Maintenance" } });
  fireEvent.change(within(form).getByLabelText("Routed to department"), { target: { value: "4" } });
  expect(screen.getByText(/Only complaints filed after this change/)).toBeInTheDocument();
  fireEvent.click(within(form).getByRole("button", { name: "Save category" }));

  expect(await screen.findByText("Potholes updated.")).toBeInTheDocument();
  expect(departmentService.updateCategory).toHaveBeenCalledWith(9, {
    name: "Potholes", slug: "potholes", description: null, department_id: 4,
  });
});

test("deactivation errors from the server are shown", async () => {
  await renderPage();
  vi.mocked(departmentService.updateDepartment).mockRejectedValue(
    apiError(409, "Cannot deactivate 'Roads Department': 1 active category is still mapped to it."),
  );
  const row = screen.getAllByRole("row").find((r) => within(r).queryByText("Roads Department") && within(r).queryByText("Active"))!;
  fireEvent.click(within(row).getByRole("button", { name: "Deactivate" }));
  expect(await screen.findByRole("alert")).toHaveTextContent("1 active category is still mapped to it");
  expect(departmentService.updateDepartment).toHaveBeenCalledWith(1, { is_active: false });
});
