import { fireEvent, screen } from "@testing-library/react";
import { AxiosError, AxiosHeaders } from "axios";
import { vi } from "vitest";

import * as authService from "../services/authService";
import { listCategories } from "../services/complaintService";
import { fetchReport, saveBlob } from "../services/reportService";
import { tokenStorage } from "../services/tokenStorage";
import { renderWithAuth } from "../test/renderWithAuth";
import type { UserRole } from "../types/auth";
import ReportsPage from "./ReportsPage";

vi.mock("../services/authService");
vi.mock("../services/complaintService");
vi.mock("../services/reportService");

function renderAs(role: UserRole) {
  tokenStorage.save({ access_token: "a", refresh_token: "r" });
  vi.mocked(authService.fetchCurrentUser).mockResolvedValue({
    id: 1, full_name: "Ravi Kumar", email: "ravi@example.com", role, is_active: true,
    created_at: "2026-10-01T00:00:00Z", last_login_at: null,
  });
  vi.mocked(listCategories).mockResolvedValue([
    { id: 3, name: "Drainage", slug: "drainage", description: null, department: { id: 8, name: "Sewerage Dept" } },
  ]);
  return renderWithAuth(<ReportsPage />, { path: "/app/reports", route: "/app/reports" });
}

beforeEach(() => localStorage.clear());
afterEach(() => vi.resetAllMocks());

test("downloads a PDF with the chosen filters", async () => {
  const blob = new Blob(["%PDF-1.4"], { type: "application/pdf" });
  vi.mocked(fetchReport).mockResolvedValue({ blob, filename: "complaints-2026-10-10.pdf" });
  renderAs("user");

  await screen.findByRole("heading", { name: "Reports" });
  expect(screen.queryByLabelText("Department")).not.toBeInTheDocument();
  fireEvent.change(screen.getByLabelText("From date"), { target: { value: "2026-10-01" } });
  fireEvent.change(screen.getByLabelText("Status"), { target: { value: "resolved" } });
  fireEvent.click(screen.getByRole("button", { name: "Download PDF" }));

  expect(await screen.findByText("Downloaded complaints-2026-10-10.pdf.")).toBeInTheDocument();
  expect(fetchReport).toHaveBeenCalledWith("pdf", expect.objectContaining({ date_from: "2026-10-01", status: "resolved" }));
  expect(saveBlob).toHaveBeenCalledWith({ blob, filename: "complaints-2026-10-10.pdf" });
});

test("admins can filter by department and download Excel", async () => {
  const blob = new Blob(["xlsx"]);
  vi.mocked(fetchReport).mockResolvedValue({ blob, filename: "complaints-2026-10-10.xlsx" });
  renderAs("admin");

  const department = await screen.findByLabelText("Department");
  await screen.findByRole("option", { name: "Sewerage Dept" });
  fireEvent.change(department, { target: { value: "8" } });
  fireEvent.click(screen.getByRole("button", { name: "Download Excel" }));

  expect(await screen.findByText("Downloaded complaints-2026-10-10.xlsx.")).toBeInTheDocument();
  expect(fetchReport).toHaveBeenCalledWith("xlsx", expect.objectContaining({ department_id: 8 }));
});

test("shows the server error when a download fails", async () => {
  vi.mocked(fetchReport).mockRejectedValue(
    new AxiosError("Bad Request", "ERR_BAD_REQUEST", undefined, undefined, {
      status: 400, statusText: "Bad Request", data: { detail: "The start date must be on or before the end date." },
      headers: {}, config: { headers: new AxiosHeaders() },
    }),
  );
  renderAs("user");
  fireEvent.click(await screen.findByRole("button", { name: "Download Excel" }));
  expect(await screen.findByRole("alert")).toHaveTextContent("The start date must be on or before the end date.");
  expect(saveBlob).not.toHaveBeenCalled();
});

test("rejects a reversed date range without calling the server", async () => {
  renderAs("user");
  await screen.findByRole("heading", { name: "Reports" });
  fireEvent.change(screen.getByLabelText("From date"), { target: { value: "2026-10-05" } });
  fireEvent.change(screen.getByLabelText("To date"), { target: { value: "2026-10-01" } });
  fireEvent.click(screen.getByRole("button", { name: "Download PDF" }));
  expect(await screen.findByRole("alert")).toHaveTextContent("start date must be on or before");
  expect(fetchReport).not.toHaveBeenCalled();
});
