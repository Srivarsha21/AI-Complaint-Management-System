import { fireEvent, screen, waitFor } from "@testing-library/react";
import { vi } from "vitest";

import * as authService from "../../services/authService";
import * as complaintService from "../../services/complaintService";
import * as departmentService from "../../services/departmentService";
import { tokenStorage } from "../../services/tokenStorage";
import { renderWithAuth } from "../../test/renderWithAuth";
import type { User } from "../../types/auth";
import type { ComplaintDetail } from "../../types/complaint";
import AssignmentCard from "./AssignmentCard";

vi.mock("../../services/authService");
vi.mock("../../services/complaintService");
vi.mock("../../services/departmentService");

const SEWERAGE = { id: 3, name: "Sewerage Dept" };
const ROADS = { id: 4, name: "Roads Dept" };

function makeComplaint(overrides: Partial<ComplaintDetail> = {}): ComplaintDetail {
  return {
    id: 5, reference_number: "CMP-2026-000005", subject: "Blocked drain", description: "Drain blocked for a week.",
    status: "submitted", priority: null, category: { id: 1, name: "Drainage" }, department: SEWERAGE,
    location_text: "Ameerpet", latitude: null, longitude: null, incident_at: null, resolved_at: null, closed_at: null,
    user: { id: 7, full_name: "Ravi Kumar", role: "user" }, assigned_to: null,
    created_at: "2026-10-09T10:00:00Z", updated_at: "2026-10-09T10:00:00Z",
    history: [], comments: [], attachments: [], allowed_transitions: ["assigned", "closed"],
    assignments: [], can_manage: true,
    ...overrides,
  };
}

function signIn(overrides: Partial<User>) {
  tokenStorage.save({ access_token: "a", refresh_token: "r" });
  vi.mocked(authService.fetchCurrentUser).mockResolvedValue({
    id: 20, full_name: "Officer", email: "officer@example.com", role: "staff", is_active: true,
    created_at: "2026-10-01T00:00:00Z", last_login_at: null, department: SEWERAGE, ...overrides,
  });
}

function renderCard(complaint: ComplaintDetail, onUpdated = vi.fn()) {
  renderWithAuth(<AssignmentCard complaint={complaint} onUpdated={onUpdated} />);
  return onUpdated;
}

beforeEach(() => localStorage.clear());
afterEach(() => vi.resetAllMocks());

test("renders nothing for people who do not manage the complaint", async () => {
  signIn({ role: "user", department: null });
  renderCard(makeComplaint({ can_manage: false }));
  await waitFor(() => expect(authService.fetchCurrentUser).toHaveBeenCalled());
  expect(screen.queryByText("Assignment")).not.toBeInTheDocument();
  expect(departmentService.listDepartmentStaff).not.toHaveBeenCalled();
});

test("staff assign within their own department and cannot re-route", async () => {
  signIn({ role: "staff" });
  vi.mocked(departmentService.listDepartmentStaff).mockResolvedValue([
    { id: 21, full_name: "Asha Reddy", role: "staff" },
    { id: 22, full_name: "Kiran Rao", role: "staff" },
  ]);
  const updated = makeComplaint({ status: "assigned", assigned_to: { id: 22, full_name: "Kiran Rao", role: "staff" } });
  vi.mocked(complaintService.assignComplaint).mockResolvedValue(updated);
  const onUpdated = renderCard(makeComplaint());

  expect(await screen.findByRole("option", { name: "Kiran Rao" })).toBeInTheDocument();
  expect(departmentService.listDepartmentStaff).toHaveBeenCalledWith(3);
  expect(screen.queryByLabelText("Route to department")).not.toBeInTheDocument();
  expect(departmentService.listDepartments).not.toHaveBeenCalled();

  fireEvent.click(screen.getByRole("button", { name: "Assign" }));
  expect(await screen.findByText("Choose a staff member.")).toBeInTheDocument();
  expect(complaintService.assignComplaint).not.toHaveBeenCalled();

  fireEvent.change(screen.getByLabelText("Assign to staff member"), { target: { value: "22" } });
  fireEvent.change(screen.getByLabelText("Note (optional)"), { target: { value: "Ward 12 crew" } });
  fireEvent.click(screen.getByRole("button", { name: "Assign" }));

  await waitFor(() => expect(onUpdated).toHaveBeenCalledWith(updated));
  expect(complaintService.assignComplaint).toHaveBeenCalledWith(5, { department_id: undefined, assignee_id: 22, note: "Ward 12 crew" });
});

test("admins can re-route to another department and pick its staff", async () => {
  signIn({ id: 1, role: "admin", department: null });
  vi.mocked(departmentService.listDepartments).mockResolvedValue([
    { ...SEWERAGE, description: null, contact_email: null, is_active: true, created_at: "", updated_at: "" },
    { ...ROADS, description: null, contact_email: null, is_active: true, created_at: "", updated_at: "" },
    { id: 9, name: "Closed Dept", description: null, contact_email: null, is_active: false, created_at: "", updated_at: "" },
  ]);
  vi.mocked(departmentService.listDepartmentStaff).mockImplementation(async (id) =>
    id === ROADS.id ? [{ id: 30, full_name: "Road Officer", role: "staff" }] : [],
  );
  vi.mocked(complaintService.assignComplaint).mockResolvedValue(makeComplaint({ department: ROADS }));
  renderCard(makeComplaint());

  const department = await screen.findByLabelText("Route to department");
  expect(await screen.findByRole("option", { name: "Roads Dept" })).toBeInTheDocument();
  expect(screen.queryByRole("option", { name: "Closed Dept" })).not.toBeInTheDocument();

  fireEvent.change(department, { target: { value: String(ROADS.id) } });
  expect(await screen.findByRole("option", { name: "Road Officer" })).toBeInTheDocument();
  fireEvent.change(screen.getByLabelText("Assign to staff member (optional)"), { target: { value: "30" } });
  fireEvent.click(screen.getByRole("button", { name: "Re-route complaint" }));

  await waitFor(() =>
    expect(complaintService.assignComplaint).toHaveBeenCalledWith(5, { department_id: ROADS.id, assignee_id: 30, note: "" }),
  );
});

test("shows assignment history and hides the form for closed complaints", async () => {
  signIn({ role: "staff" });
  vi.mocked(departmentService.listDepartmentStaff).mockResolvedValue([]);
  renderCard(
    makeComplaint({
      status: "closed",
      assignments: [
        {
          id: 1, from_department: ROADS, to_department: SEWERAGE, assigned_to: null,
          assigned_by: { id: 1, full_name: "Admin One", role: "admin" }, note: "Drainage issue", created_at: "2026-10-09T11:00:00Z",
        },
      ],
    }),
  );

  expect(await screen.findByText("Re-routed Roads Dept → Sewerage Dept")).toBeInTheDocument();
  expect(screen.getByText("Drainage issue")).toBeInTheDocument();
  expect(screen.getByText("Closed complaints cannot be re-assigned.")).toBeInTheDocument();
  expect(screen.queryByRole("button", { name: "Assign" })).not.toBeInTheDocument();
});
