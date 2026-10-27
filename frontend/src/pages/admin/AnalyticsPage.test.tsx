import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { AxiosError } from "axios";
import { cloneElement, type ReactElement } from "react";
import { MemoryRouter } from "react-router-dom";
import { vi } from "vitest";

import { listCategories } from "../../services/complaintService";
import { getAnalytics } from "../../services/dashboardService";
import type { Analytics } from "../../types/analytics";
import AnalyticsPage from "./AnalyticsPage";

vi.mock("../../services/dashboardService");
vi.mock("../../services/complaintService");

// Recharts' ResponsiveContainer needs ResizeObserver, which jsdom lacks.
class ResizeObserverStub {
  observe() {}
  unobserve() {}
  disconnect() {}
}
vi.stubGlobal("ResizeObserver", ResizeObserverStub);

// jsdom has no layout, so give charts a fixed size and let them render real SVG.
vi.mock("recharts", async (importOriginal) => {
  const actual = await importOriginal<typeof import("recharts")>();
  return {
    ...actual,
    ResponsiveContainer: ({ children }: { children: ReactElement<{ width?: number; height?: number }> }) =>
      cloneElement(children, { width: 600, height: 250 }),
  };
});

function makeAnalytics(overrides: Partial<Analytics> = {}): Analytics {
  return {
    generated_at: "2026-10-10T06:00:00Z",
    filters: { date_from: null, date_to: null, category_id: null, department_id: null, status: null, timezone: "Asia/Kolkata" },
    totals: { total: 5, open: 3, pending: 2, in_progress: 1, resolved: 1, closed: 1 },
    by_status: [
      { status: "submitted", count: 1 },
      { status: "assigned", count: 1 },
      { status: "in_progress", count: 1 },
      { status: "resolved", count: 1 },
      { status: "closed", count: 1 },
    ],
    by_priority: [
      { priority: "low", count: 1 },
      { priority: "medium", count: 0 },
      { priority: "high", count: 1 },
      { priority: "critical", count: 1 },
      { priority: "not_assessed", count: 2 },
    ],
    by_category: [
      { id: 1, name: "Drainage", count: 3 },
      { id: 2, name: "Potholes", count: 2 },
    ],
    by_department: [
      { id: 1, name: "Sewerage Dept", count: 2 },
      { id: 2, name: "Roads Dept", count: 2 },
      { id: null, name: "Unassigned", count: 1 },
    ],
    trend: {
      granularity: "day",
      points: [
        { period_start: "2026-10-01", created: 2, resolved: 1 },
        { period_start: "2026-10-02", created: 3, resolved: 0 },
      ],
    },
    resolution: { average_hours: 20, median_hours: 18.5, sample_size: 2 },
    oldest_open: [
      {
        id: 2, reference_number: "CMP-2026-000002", subject: "Overflowing drain", status: "submitted", priority: null,
        category: "Drainage", department: null, created_at: "2026-10-01T18:00:00Z", age_days: 8,
      },
    ],
    ...overrides,
  };
}

function renderPage() {
  return render(
    <MemoryRouter>
      <AnalyticsPage />
    </MemoryRouter>,
  );
}

beforeEach(() => {
  vi.mocked(listCategories).mockResolvedValue([
    { id: 1, name: "Drainage", slug: "drainage", description: null, department: { id: 1, name: "Sewerage Dept" } },
    { id: 2, name: "Potholes", slug: "potholes", description: null, department: { id: 2, name: "Roads Dept" } },
  ]);
});
afterEach(() => vi.resetAllMocks());

test("renders KPIs, chart summaries and the oldest open complaints", async () => {
  vi.mocked(getAnalytics).mockResolvedValue(makeAnalytics());
  renderPage();

  const total = (await screen.findByText("Total complaints")).closest("[data-stat]") as HTMLElement;
  expect(within(total).getByText("5")).toBeInTheDocument();
  expect(screen.getByText("2 pending · 1 in progress")).toBeInTheDocument();
  expect(screen.getByText("20.0 hours")).toBeInTheDocument();
  expect(screen.getByText(/Median 18.5 hours · based on 2 resolved complaints/)).toBeInTheDocument();

  expect(screen.getByRole("heading", { name: "Complaints by category" })).toBeInTheDocument();
  expect(screen.getByText("Drainage has the most complaints (3 of 5). 2 categories in these results.")).toBeInTheDocument();
  expect(screen.getByText(/Not assessed: 2/)).toBeInTheDocument();
  expect(screen.getByRole("img", { name: /Created vs resolved per day/ })).toBeInTheDocument();
  expect(screen.getByText(/5 created, 1 resolved/)).toBeInTheDocument();
  // The charts themselves render as SVG.
  expect(document.querySelectorAll(".recharts-wrapper > svg.recharts-surface").length).toBe(5);

  const oldest = screen.getByRole("link", { name: "CMP-2026-000002" });
  expect(oldest).toHaveAttribute("href", "/app/complaints/2");
  expect(screen.getByText("8 days")).toBeInTheDocument();
});

test("shows an empty state when nothing matches", async () => {
  vi.mocked(getAnalytics).mockResolvedValue(
    makeAnalytics({
      totals: { total: 0, open: 0, pending: 0, in_progress: 0, resolved: 0, closed: 0 },
      by_category: [], by_department: [], oldest_open: [],
      trend: { granularity: "day", points: [] },
      resolution: { average_hours: null, median_hours: null, sample_size: 0 },
    }),
  );
  renderPage();

  expect(await screen.findByText(/No complaints match these filters/)).toBeInTheDocument();
  expect(screen.getByText("No resolved complaints yet")).toBeInTheDocument();
  expect(screen.queryByRole("heading", { name: "Complaints by category" })).not.toBeInTheDocument();
});

test("applies filters and validates the date range", async () => {
  vi.mocked(getAnalytics).mockResolvedValue(makeAnalytics());
  renderPage();
  await screen.findByText("Total complaints");

  fireEvent.change(screen.getByLabelText("From date"), { target: { value: "2026-10-05" } });
  fireEvent.change(screen.getByLabelText("To date"), { target: { value: "2026-10-01" } });
  fireEvent.click(screen.getByRole("button", { name: "Apply filters" }));
  expect(screen.getByRole("alert")).toHaveTextContent("start date must be on or before");
  expect(getAnalytics).toHaveBeenCalledTimes(1);

  fireEvent.change(screen.getByLabelText("To date"), { target: { value: "2026-10-31" } });
  fireEvent.change(screen.getByLabelText("Status"), { target: { value: "resolved" } });
  fireEvent.click(screen.getByRole("button", { name: "Apply filters" }));
  await waitFor(() => expect(getAnalytics).toHaveBeenCalledTimes(2));
  expect(vi.mocked(getAnalytics).mock.calls[1][0]).toMatchObject({
    date_from: "2026-10-05", date_to: "2026-10-31", status: "resolved",
  });
  await waitFor(() => expect(screen.queryByText("Updating…")).not.toBeInTheDocument());
});

test("shows an error when analytics cannot be loaded", async () => {
  vi.mocked(getAnalytics).mockRejectedValue(new AxiosError("Network Error"));
  renderPage();
  expect(await screen.findByRole("alert")).toHaveTextContent("Could not load analytics");
});
