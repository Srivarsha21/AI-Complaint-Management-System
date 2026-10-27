import { fireEvent, render, screen } from "@testing-library/react";
import { vi } from "vitest";

import * as aiService from "../../services/aiService";
import type { ComplaintDetail } from "../../types/complaint";
import PriorityOverride from "./PriorityOverride";

vi.mock("../../services/aiService");

const COMPLAINT = { id: 5, priority: "medium", priority_source: "ai" } as ComplaintDetail;

afterEach(() => vi.resetAllMocks());

test("staff can override the AI-predicted priority with a note", async () => {
  const updated = { ...COMPLAINT, priority: "critical", priority_source: "staff" } as ComplaintDetail;
  vi.mocked(aiService.overridePriority).mockResolvedValue(updated);
  const onUpdated = vi.fn();
  render(<PriorityOverride complaint={COMPLAINT} onUpdated={onUpdated} />);

  expect(screen.getByLabelText("Priority")).toHaveValue("medium");
  fireEvent.change(screen.getByLabelText("Priority"), { target: { value: "critical" } });
  fireEvent.change(screen.getByLabelText("Note (optional)"), { target: { value: "Hospital next door" } });
  fireEvent.click(screen.getByRole("button", { name: "Save priority" }));

  await vi.waitFor(() => expect(onUpdated).toHaveBeenCalledWith(updated));
  expect(aiService.overridePriority).toHaveBeenCalledWith(5, "critical", "Hospital next door");
});

test("shows the server error when the override fails", async () => {
  vi.mocked(aiService.overridePriority).mockRejectedValue(new Error("nope"));
  render(<PriorityOverride complaint={COMPLAINT} onUpdated={vi.fn()} />);

  fireEvent.click(screen.getByRole("button", { name: "Save priority" }));
  expect(await screen.findByText("Something went wrong. Please try again.")).toBeInTheDocument();
});

test("save is disabled when the staff-set priority is unchanged", () => {
  render(<PriorityOverride complaint={{ ...COMPLAINT, priority_source: "staff" } as ComplaintDetail} onUpdated={vi.fn()} />);
  expect(screen.getByRole("button", { name: "Save priority" })).toBeDisabled();
});
