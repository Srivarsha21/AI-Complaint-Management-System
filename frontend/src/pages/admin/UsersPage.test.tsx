import { fireEvent, screen, waitFor } from "@testing-library/react";
import { vi } from "vitest";

import * as adminService from "../../services/adminService";
import * as authService from "../../services/authService";
import * as departmentService from "../../services/departmentService";
import { tokenStorage } from "../../services/tokenStorage";
import { renderWithAuth } from "../../test/renderWithAuth";
import type { User } from "../../types/auth";
import UsersPage from "./UsersPage";

vi.mock("../../services/adminService");
vi.mock("../../services/authService");
vi.mock("../../services/departmentService");

const BASE = { is_active: true, created_at: "2026-10-01T00:00:00Z", last_login_at: null };
const ADMIN: User = { ...BASE, id: 1, full_name: "Admin One", email: "admin@example.com", role: "admin" };
const RAVI: User = { ...BASE, id: 2, full_name: "Ravi Kumar", email: "ravi@example.com", role: "user", department: null };
const ROADS = { id: 4, name: "Roads Dept", description: null, contact_email: null, is_active: true, created_at: "", updated_at: "" };

beforeEach(() => {
  localStorage.clear();
  tokenStorage.save({ access_token: "a", refresh_token: "r" });
  vi.mocked(authService.fetchCurrentUser).mockResolvedValue(ADMIN);
  vi.mocked(adminService.listUsers).mockResolvedValue({ items: [ADMIN, RAVI], total: 2 });
  vi.mocked(departmentService.listDepartments).mockResolvedValue([ROADS]);
});
afterEach(() => vi.resetAllMocks());

test("making someone staff requires choosing a department", async () => {
  vi.mocked(adminService.updateUser).mockResolvedValue({ ...RAVI, role: "staff", department: { id: 4, name: "Roads Dept" } });
  renderWithAuth(<UsersPage />);

  fireEvent.change(await screen.findByLabelText("Role for Ravi Kumar"), { target: { value: "staff" } });
  fireEvent.click(screen.getByRole("button", { name: "Make staff" }));
  expect(await screen.findByText("Choose a department for this staff member.")).toBeInTheDocument();
  expect(adminService.updateUser).not.toHaveBeenCalled();

  fireEvent.change(screen.getByLabelText("Department for Ravi Kumar"), { target: { value: "4" } });
  fireEvent.click(screen.getByRole("button", { name: "Make staff" }));

  expect(await screen.findByText("Ravi Kumar: now staff of Roads Dept.")).toBeInTheDocument();
  expect(adminService.updateUser).toHaveBeenCalledWith(2, { role: "staff", department_id: 4 });
  await waitFor(() => expect(screen.queryByRole("button", { name: "Make staff" })).not.toBeInTheDocument());
});
