import { fireEvent, screen } from "@testing-library/react";
import { vi } from "vitest";

import * as aiService from "../../services/aiService";
import * as authService from "../../services/authService";
import * as complaintService from "../../services/complaintService";
import { tokenStorage } from "../../services/tokenStorage";
import { renderWithAuth } from "../../test/renderWithAuth";
import type { ComplaintDetail } from "../../types/complaint";
import ComplaintDetailPage from "./ComplaintDetailPage";

vi.mock("../../services/authService");
vi.mock("../../services/complaintService");
vi.mock("../../services/aiService");

const OWNER = { id: 7, full_name: "Ravi Kumar", role: "user" as const };

function makeComplaint(overrides: Partial<ComplaintDetail> = {}): ComplaintDetail {
  return {
    id: 5,
    reference_number: "CMP-2026-000005",
    subject: "Street light not working",
    description: "The light at the corner has been off for a week.",
    status: "resolved",
    priority: null,
    category: { id: 4, name: "Street Lights" },
    department: { id: 4, name: "Street Lighting Department" },
    location_text: "SR Nagar, Hyderabad",
    latitude: null,
    longitude: null,
    incident_at: null,
    resolved_at: "2026-10-10T10:00:00Z",
    closed_at: null,
    user: OWNER,
    created_at: "2026-10-09T10:00:00Z",
    updated_at: "2026-10-10T10:00:00Z",
    history: [
      { id: 1, from_status: null, to_status: "submitted", note: null, changed_by: OWNER, created_at: "2026-10-09T10:00:00Z" },
      { id: 2, from_status: "in_progress", to_status: "resolved", note: "Bulb replaced.", changed_by: null, created_at: "2026-10-10T10:00:00Z" },
    ],
    comments: [],
    attachments: [],
    allowed_transitions: ["in_progress", "closed"],
    assignments: [],
    can_manage: false,
    ...overrides,
  };
}

function renderDetail() {
  tokenStorage.save({ access_token: "a", refresh_token: "r" });
  vi.mocked(authService.fetchCurrentUser).mockResolvedValue({
    ...OWNER, email: "ravi@example.com", is_active: true, created_at: "2026-10-01T00:00:00Z", last_login_at: null,
  });
  return renderWithAuth(<ComplaintDetailPage />, { path: "/app/complaints/:id", route: "/app/complaints/5" });
}

beforeEach(() => localStorage.clear());
afterEach(() => vi.resetAllMocks());

test("shows complaint details, history notes and owner actions", async () => {
  vi.mocked(complaintService.getComplaint).mockResolvedValue(makeComplaint());
  renderDetail();

  expect(await screen.findByText("Street light not working")).toBeInTheDocument();
  expect(screen.getByText("Bulb replaced.")).toBeInTheDocument();
  expect(screen.getByText("Was your problem resolved?")).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Confirm resolved & close" })).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Reopen" })).toBeInTheDocument();
});

test("reopening requires a reason before calling the API", async () => {
  vi.mocked(complaintService.getComplaint).mockResolvedValue(makeComplaint());
  vi.mocked(complaintService.changeStatus).mockResolvedValue(makeComplaint({ status: "in_progress", allowed_transitions: [] }));
  renderDetail();

  fireEvent.click(await screen.findByRole("button", { name: "Reopen" }));
  fireEvent.click(screen.getByRole("button", { name: "Confirm: In progress" }));
  expect(await screen.findByText("Please add a note explaining this change.")).toBeInTheDocument();
  expect(complaintService.changeStatus).not.toHaveBeenCalled();

  fireEvent.change(screen.getByLabelText("Note (required)"), { target: { value: "Light is off again." } });
  fireEvent.click(screen.getByRole("button", { name: "Confirm: In progress" }));

  expect(await screen.findByText("In progress", { selector: "span" })).toBeInTheDocument();
  expect(complaintService.changeStatus).toHaveBeenCalledWith(5, "in_progress", "Light is off again.");
});

test("hides the action panel when no transitions are allowed", async () => {
  vi.mocked(complaintService.getComplaint).mockResolvedValue(makeComplaint({ status: "submitted", allowed_transitions: [] }));
  renderDetail();

  await screen.findByText("Street light not working");
  expect(screen.queryByText("Update status")).not.toBeInTheDocument();
});

test("shows a not-found message for inaccessible complaints", async () => {
  vi.mocked(complaintService.getComplaint).mockRejectedValue(new Error("404"));
  renderDetail();
  expect(await screen.findByRole("alert")).toBeInTheDocument();
});

test("labels an AI-predicted priority and shows the AI card and override only to staff", async () => {
  vi.mocked(complaintService.getComplaint).mockResolvedValue(
    makeComplaint({ priority: "high", priority_source: "ai", can_manage: true }),
  );
  vi.mocked(aiService.getComplaintAi).mockResolvedValue({
    complaint_id: 5,
    prediction: {
      predicted_category: { id: 4, name: "Street Lights", slug: "street-lights", confidence: 0.92 },
      predicted_priority: "high",
      priority_factors: ["Category baseline (Street Lights): medium"],
      sentiment_label: "negative",
      sentiment_score: -0.33,
      urgency_score: 0,
      possible_emergency: false,
      duplicate_candidates: [],
      model_version: "tfidf-logreg-test",
      user_accepted_category: true,
      created_at: "2026-10-09T10:00:00Z",
    },
    priority: "high",
    priority_source: "ai",
    similar: [
      { reference_number: "CMP-2026-000002", status: "submitted", similarity: 0.61, complaint_id: 2, subject: "Lamp off", distance_m: 40 },
    ],
    model_status: "ready",
    disclaimer: "Synthetic data.",
  });
  tokenStorage.save({ access_token: "a", refresh_token: "r" });
  vi.mocked(authService.fetchCurrentUser).mockResolvedValue({
    id: 1, full_name: "Admin", role: "admin", email: "admin@example.com", is_active: true,
    created_at: "2026-10-01T00:00:00Z", last_login_at: null,
  });
  renderWithAuth(<ComplaintDetailPage />, { path: "/app/complaints/:id", route: "/app/complaints/5" });

  expect(await screen.findByText("Priority (AI-predicted)")).toBeInTheDocument();
  expect(await screen.findByText("Street Lights (92% confidence)")).toBeInTheDocument();
  expect(screen.getByRole("link", { name: "CMP-2026-000002" })).toHaveAttribute("href", "/app/complaints/2");
  expect(screen.getByLabelText("Priority")).toHaveValue("high");
});

test("owners see the priority label but no AI card", async () => {
  vi.mocked(complaintService.getComplaint).mockResolvedValue(makeComplaint({ priority: "low", priority_source: "staff" }));
  renderDetail();
  expect(await screen.findByText("Priority (set by staff)")).toBeInTheDocument();
  expect(screen.queryByText("AI analysis")).not.toBeInTheDocument();
  expect(aiService.getComplaintAi).not.toHaveBeenCalled();
});
