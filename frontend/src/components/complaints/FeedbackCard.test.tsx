import { fireEvent, screen } from "@testing-library/react";
import { vi } from "vitest";

import * as authService from "../../services/authService";
import * as feedbackService from "../../services/feedbackService";
import { tokenStorage } from "../../services/tokenStorage";
import { renderWithAuth } from "../../test/renderWithAuth";
import type { ComplaintDetail } from "../../types/complaint";
import FeedbackCard from "./FeedbackCard";

vi.mock("../../services/authService");
vi.mock("../../services/feedbackService");

const OWNER = { id: 7, full_name: "Ravi Kumar", role: "user" as const };

function complaint(status: ComplaintDetail["status"]): ComplaintDetail {
  return { id: 5, status, user: OWNER } as ComplaintDetail;
}

function renderCard(status: ComplaintDetail["status"], userId = 7) {
  tokenStorage.save({ access_token: "a", refresh_token: "r" });
  vi.mocked(authService.fetchCurrentUser).mockResolvedValue({
    ...OWNER, id: userId, email: "r@example.com", is_active: true, created_at: "2026-10-01T00:00:00Z", last_login_at: null,
  });
  return renderWithAuth(<FeedbackCard complaint={complaint(status)} />, { path: "/", route: "/" });
}

beforeEach(() => localStorage.clear());
afterEach(() => vi.resetAllMocks());

test("owner rates a resolved complaint", async () => {
  vi.mocked(feedbackService.getFeedback).mockResolvedValue(null);
  vi.mocked(feedbackService.submitFeedback).mockResolvedValue({
    id: 1, complaint_id: 5, rating: 4, resolved_satisfactorily: true, ai_helpful: null, comment: null,
    created_at: "2026-10-10T10:00:00Z",
  });
  renderCard("resolved");

  fireEvent.click(await screen.findByRole("button", { name: "Send feedback" }));
  expect(await screen.findByText(/Please choose a rating/)).toBeInTheDocument();
  expect(feedbackService.submitFeedback).not.toHaveBeenCalled();

  fireEvent.click(screen.getByRole("radio", { name: /4 stars/ }));
  fireEvent.click(screen.getByRole("button", { name: "Yes" }));
  fireEvent.click(screen.getByRole("button", { name: "Send feedback" }));

  expect(await screen.findByText("Your feedback")).toBeInTheDocument();
  expect(feedbackService.submitFeedback).toHaveBeenCalledWith(5, {
    rating: 4, resolved_satisfactorily: true, ai_helpful: null, comment: "",
  });
});

test("shows existing feedback instead of the form", async () => {
  vi.mocked(feedbackService.getFeedback).mockResolvedValue({
    id: 1, complaint_id: 5, rating: 5, resolved_satisfactorily: true, ai_helpful: true, comment: "Quick fix!",
    created_at: "2026-10-10T10:00:00Z",
  });
  renderCard("closed");
  expect(await screen.findByText("“Quick fix!”")).toBeInTheDocument();
  expect(screen.queryByRole("button", { name: "Send feedback" })).not.toBeInTheDocument();
});

test("hidden before resolution and for other users", async () => {
  vi.mocked(feedbackService.getFeedback).mockResolvedValue(null);
  const { unmount } = renderCard("in_progress");
  await new Promise((r) => setTimeout(r, 50));
  expect(screen.queryByText("How did we do?")).not.toBeInTheDocument();
  expect(feedbackService.getFeedback).not.toHaveBeenCalled();
  unmount();

  renderCard("resolved", 99);
  await new Promise((r) => setTimeout(r, 50));
  expect(screen.queryByText("How did we do?")).not.toBeInTheDocument();
});
