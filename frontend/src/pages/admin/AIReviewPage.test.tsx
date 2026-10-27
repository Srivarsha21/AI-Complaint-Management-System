import { fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { vi } from "vitest";

import * as complaintService from "../../services/complaintService";
import * as feedbackService from "../../services/feedbackService";
import type { AIReviewItem } from "../../types/feedback";
import AIReviewPage from "./AIReviewPage";

vi.mock("../../services/complaintService");
vi.mock("../../services/feedbackService");

const ITEM: AIReviewItem = {
  prediction_id: 11,
  complaint: { id: 3, reference_number: "CMP-2026-000003", subject: "Open manhole on colony road", status: "in_progress" },
  final_category: { id: 1, name: "Drainage & Sewerage" },
  predicted_category: { id: 3, name: "Roads & Potholes" },
  category_confidence: 0.44,
  user_accepted_category: false,
  predicted_priority: "high",
  final_priority: "critical",
  priority_source: "staff",
  signals: ["category_changed", "suggestion_rejected", "priority_overridden"],
  review_status: "unreviewed",
  corrected_category: null,
  review_note: null,
  reviewed_at: null,
  model_version: "tfidf-logreg-test",
};

beforeEach(() => {
  vi.mocked(complaintService.listCategories).mockResolvedValue([]);
  vi.mocked(feedbackService.listAIReviews).mockResolvedValue({ items: [ITEM], total: 1 });
  vi.mocked(feedbackService.getQualitySummary).mockResolvedValue({
    predictions: 40, with_category_suggestion: 40, category_agreement_rate: 0.85, suggestion_acceptance_rate: 0.7,
    priority_overrides: 1, reviewed: 0, marked_incorrect: 0, feedback_count: 6, average_rating: 4.2,
    satisfied_rate: 0.83, ai_helpful_rate: 0.75,
  });
});
afterEach(() => vi.resetAllMocks());

test("lists flagged predictions with signals and records a review", async () => {
  vi.mocked(feedbackService.reviewPrediction).mockResolvedValue({ ...ITEM, review_status: "incorrect" });
  render(
    <MemoryRouter>
      <AIReviewPage />
    </MemoryRouter>,
  );

  expect(await screen.findByText("Open manhole on colony road")).toBeInTheDocument();
  expect(screen.getByText("Category differs")).toBeInTheDocument();
  expect(screen.getByText("Priority overridden")).toBeInTheDocument();
  expect(screen.getByText("85%")).toBeInTheDocument();
  expect(screen.getByText("4.2 ★")).toBeInTheDocument();

  fireEvent.click(screen.getByRole("button", { name: "✗ Incorrect" }));
  expect(await screen.findByText("CMP-2026-000003 marked incorrect.")).toBeInTheDocument();
  expect(feedbackService.reviewPrediction).toHaveBeenCalledWith(11, { review_status: "incorrect", corrected_category_id: null, note: "" });
});
