import { fireEvent, render, screen } from "@testing-library/react";
import { vi } from "vitest";

import * as aiService from "../../services/aiService";
import type { AnalyzeResult } from "../../types/ai";
import AiSuggestionPanel from "./AiSuggestionPanel";

vi.mock("../../services/aiService");

function makeResult(overrides: Partial<AnalyzeResult> = {}): AnalyzeResult {
  return {
    model_status: "ready",
    category: { id: 6, name: "Electricity", slug: "electricity", confidence: 0.87 },
    alternatives: [{ id: 4, name: "Street Lights", slug: "street-lights", confidence: 0.08 }],
    department: { id: 6, name: "Electricity Department" },
    priority: { level: "high", factors: ["Category baseline (Electricity): medium", "Health or safety risk mentioned: bent"] },
    sentiment: { label: "negative", score: -0.4, urgency: 0.1 },
    possible_emergency: false,
    emergency_message: null,
    duplicates: [],
    model_version: "tfidf-logreg-test",
    disclaimer: "Suggestions from a model trained on a synthetic dataset.",
    ...overrides,
  };
}

const DESCRIPTION = "The electric pole near the bus stop is bent and may fall any time.";

function renderPanel(props: Partial<Parameters<typeof AiSuggestionPanel>[0]> = {}) {
  const onUseCategory = vi.fn();
  const onSuggestion = vi.fn();
  render(
    <AiSuggestionPanel
      subject="Bent electric pole"
      description={DESCRIPTION}
      categoryId={null}
      onUseCategory={onUseCategory}
      onSuggestion={onSuggestion}
      autoRun={false}
      {...props}
    />,
  );
  return { onUseCategory, onSuggestion };
}

afterEach(() => vi.resetAllMocks());

test("shows the suggestion and only changes the category when the user clicks", async () => {
  vi.mocked(aiService.analyzeComplaint).mockResolvedValue(makeResult());
  const { onUseCategory, onSuggestion } = renderPanel();

  fireEvent.click(screen.getByRole("button", { name: "Analyse with AI" }));

  expect(await screen.findByText("Electricity")).toBeInTheDocument();
  expect(screen.getByText("87% confidence")).toBeInTheDocument();
  expect(screen.getByText("Electricity Department")).toBeInTheDocument();
  expect(onSuggestion).toHaveBeenCalledWith(6);
  expect(onUseCategory).not.toHaveBeenCalled();

  fireEvent.click(screen.getByRole("button", { name: "Use this category" }));
  expect(onUseCategory).toHaveBeenCalledWith(6);

  fireEvent.click(screen.getByRole("button", { name: "Use category Street Lights" }));
  expect(onUseCategory).toHaveBeenLastCalledWith(4);

  expect(aiService.analyzeComplaint).toHaveBeenCalledWith(
    expect.objectContaining({ subject: "Bent electric pole", description: DESCRIPTION, category_id: null }),
  );
});

test("labels the priority as an AI prediction and lists its factors", async () => {
  vi.mocked(aiService.analyzeComplaint).mockResolvedValue(makeResult());
  renderPanel();
  fireEvent.click(screen.getByRole("button", { name: "Analyse with AI" }));

  expect(await screen.findByTestId("ai-priority")).toHaveTextContent("High");
  expect(screen.getByText("AI-predicted, may be reviewed by staff.")).toBeInTheDocument();
  expect(screen.getByText("Health or safety risk mentioned: bent")).toBeInTheDocument();
});

test("shows the 112 emergency banner immediately from keywords, before any request", () => {
  renderPanel({ subject: "Live wire on road", description: "A live wire has fallen on the road and is sparking." });

  const banner = screen.getByRole("alert");
  expect(banner).toHaveTextContent("This may be an emergency");
  expect(banner).toHaveTextContent("112");
  expect(screen.getByRole("link", { name: "112" })).toHaveAttribute("href", "tel:112");
  expect(aiService.analyzeComplaint).not.toHaveBeenCalled();
});

test("shows the emergency banner when the server flags a possible emergency", async () => {
  vi.mocked(aiService.analyzeComplaint).mockResolvedValue(
    makeResult({ possible_emergency: true, emergency_message: "call 112" }),
  );
  renderPanel({ description: "Something very dangerous is happening near the school gate." });
  expect(screen.queryByRole("alert")).not.toBeInTheDocument();

  fireEvent.click(screen.getByRole("button", { name: "Analyse with AI" }));
  expect(await screen.findByRole("alert")).toHaveTextContent("112");
});

test("lists possible duplicates with reference, status and similarity and says filing is fine", async () => {
  vi.mocked(aiService.analyzeComplaint).mockResolvedValue(
    makeResult({
      duplicates: [
        { reference_number: "CMP-2026-000012", status: "in_progress", similarity: 0.734, complaint_id: null, subject: null, distance_m: null },
      ],
    }),
  );
  renderPanel();
  fireEvent.click(screen.getByRole("button", { name: "Analyse with AI" }));

  expect(await screen.findByText("CMP-2026-000012")).toBeInTheDocument();
  expect(screen.getByText("In progress")).toBeInTheDocument();
  expect(screen.getByText("73% similar")).toBeInTheDocument();
  expect(screen.getByText(/Filing yours anyway is fine/)).toBeInTheDocument();
});

test("explains when the model is not trained and when the request fails", async () => {
  vi.mocked(aiService.analyzeComplaint).mockResolvedValueOnce(
    makeResult({ model_status: "not_trained", category: null, alternatives: [], department: null }),
  );
  renderPanel();
  fireEvent.click(screen.getByRole("button", { name: "Analyse with AI" }));
  expect(await screen.findByText(/model has not been trained/)).toBeInTheDocument();

  vi.mocked(aiService.analyzeComplaint).mockRejectedValueOnce(new Error("boom"));
  fireEvent.click(screen.getByRole("button", { name: "Analyse again" }));
  expect(await screen.findByText(/AI suggestions are unavailable right now/)).toBeInTheDocument();
});

test("does not offer analysis for a too-short description", () => {
  renderPanel({ description: "short" });
  expect(screen.getByRole("button", { name: "Analyse with AI" })).toBeDisabled();
});
