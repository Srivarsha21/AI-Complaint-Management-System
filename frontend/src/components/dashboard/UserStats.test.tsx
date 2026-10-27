import { render, screen, within } from "@testing-library/react";
import { AxiosError } from "axios";
import { MemoryRouter } from "react-router-dom";
import { vi } from "vitest";

import { getDashboardSummary } from "../../services/dashboardService";
import type { DashboardSummary } from "../../types/analytics";
import UserStats from "./UserStats";

vi.mock("../../services/dashboardService");

const SUMMARY: DashboardSummary = {
  total: 6,
  pending: 3,
  by_status: { submitted: 2, assigned: 1, in_progress: 1, resolved: 1, closed: 1 },
  recent_updates: [
    {
      complaint_id: 4,
      reference_number: "CMP-2026-000004",
      subject: "Garbage not collected",
      from_status: "in_progress",
      to_status: "resolved",
      note: "Cleared by the sanitation team.",
      at: "2026-10-09T06:30:00Z",
    },
    {
      complaint_id: 9,
      reference_number: "CMP-2026-000009",
      subject: "Pothole near metro station",
      from_status: null,
      to_status: "submitted",
      note: null,
      at: "2026-10-08T04:00:00Z",
    },
  ],
};

function renderStats() {
  return render(
    <MemoryRouter>
      <UserStats />
    </MemoryRouter>,
  );
}

afterEach(() => vi.resetAllMocks());

function stat(label: string) {
  return screen.getByText(label).closest("[data-stat]") as HTMLElement;
}

test("shows counts and recent updates", async () => {
  vi.mocked(getDashboardSummary).mockResolvedValue(SUMMARY);
  renderStats();

  expect(await screen.findByText("Total filed")).toBeInTheDocument();
  expect(within(stat("Total filed")).getByText("6")).toBeInTheDocument();
  expect(within(stat("Pending")).getByText("3")).toBeInTheDocument();
  expect(within(stat("Pending")).getByText("2 submitted · 1 assigned")).toBeInTheDocument();
  expect(within(stat("In progress")).getByText("1")).toBeInTheDocument();

  expect(screen.getByText("Garbage not collected")).toBeInTheDocument();
  expect(screen.getByText(/In progress → Resolved/)).toBeInTheDocument();
  expect(screen.getByText(/Cleared by the sanitation team/)).toBeInTheDocument();
  expect(screen.getByText(/Complaint submitted/)).toBeInTheDocument();
  expect(screen.getByRole("link", { name: /Garbage not collected/ })).toHaveAttribute("href", "/app/complaints/4");
});

test("shows an empty state when there are no updates", async () => {
  vi.mocked(getDashboardSummary).mockResolvedValue({
    total: 0, pending: 0, by_status: { submitted: 0, assigned: 0, in_progress: 0, resolved: 0, closed: 0 }, recent_updates: [],
  });
  renderStats();
  expect(await screen.findByText(/No updates yet/)).toBeInTheDocument();
});

test("shows an error when the summary cannot be loaded", async () => {
  vi.mocked(getDashboardSummary).mockRejectedValue(new AxiosError("Network Error"));
  renderStats();
  expect(await screen.findByRole("alert")).toHaveTextContent("Cannot reach the server");
});
