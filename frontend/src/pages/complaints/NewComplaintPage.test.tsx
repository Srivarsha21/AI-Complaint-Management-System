import { fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { vi } from "vitest";

import * as aiService from "../../services/aiService";
import * as complaintService from "../../services/complaintService";
import type { AnalyzeResult } from "../../types/ai";
import type { ComplaintDetail } from "../../types/complaint";
import NewComplaintPage from "./NewComplaintPage";

vi.mock("../../services/complaintService");
vi.mock("../../services/aiService");

const CATEGORY = {
  id: 3,
  name: "Drainage & Sewerage",
  slug: "drainage-sewerage",
  description: "Blocked drains.",
  department: { id: 1, name: "Sewerage & Drainage Department" },
};

function renderPage() {
  return render(
    <MemoryRouter>
      <NewComplaintPage />
    </MemoryRouter>,
  );
}

beforeEach(() => {
  vi.mocked(complaintService.listCategories).mockResolvedValue([CATEGORY]);
  // jsdom lacks object URLs.
  URL.createObjectURL = vi.fn(() => "blob:preview");
  URL.revokeObjectURL = vi.fn();
});
afterEach(() => vi.resetAllMocks());

async function fillValidForm() {
  await screen.findByRole("option", { name: CATEGORY.name });
  fireEvent.change(screen.getByLabelText("Subject"), { target: { value: "Drain overflowing near bus stop" } });
  fireEvent.change(screen.getByLabelText("Description"), {
    target: { value: "Dirty water has been overflowing onto the road for three days." },
  });
  fireEvent.change(screen.getByLabelText("Category"), { target: { value: "3" } });
  fireEvent.change(screen.getByLabelText("Address or nearest landmark"), { target: { value: "Ameerpet, Hyderabad" } });
}

test("shows validation errors and does not submit an incomplete form", async () => {
  renderPage();
  await screen.findByRole("option", { name: CATEGORY.name });

  fireEvent.click(screen.getByRole("button", { name: "Submit complaint" }));

  expect(await screen.findByText("Subject must be at least 5 characters.")).toBeInTheDocument();
  expect(screen.getByText("Please describe the problem in at least 20 characters.")).toBeInTheDocument();
  expect(screen.getByText("Choose a category.")).toBeInTheDocument();
  expect(complaintService.createComplaint).not.toHaveBeenCalled();
});

test("shows the routed department once a category is chosen", async () => {
  renderPage();
  await fillValidForm();
  expect(screen.getByText("Sewerage & Drainage Department")).toBeInTheDocument();
});

test("rejects unsupported attachment types on the client", async () => {
  renderPage();
  await screen.findByRole("option", { name: CATEGORY.name });
  const input = document.querySelector('input[type="file"]') as HTMLInputElement;

  fireEvent.change(input, { target: { files: [new File(["x"], "notes.pdf", { type: "application/pdf" })] } });

  expect(await screen.findByText('"notes.pdf" is not a JPEG, PNG or WebP image.')).toBeInTheDocument();
});

test("submits and shows the reference number", async () => {
  vi.mocked(complaintService.createComplaint).mockResolvedValue({
    id: 42,
    reference_number: "CMP-2026-000042",
    department: { id: 1, name: "Sewerage & Drainage Department" },
  } as ComplaintDetail);
  renderPage();
  await fillValidForm();
  const input = document.querySelector('input[type="file"]') as HTMLInputElement;
  fireEvent.change(input, { target: { files: [new File(["png"], "drain.png", { type: "image/png" })] } });

  fireEvent.click(screen.getByRole("button", { name: "Submit complaint" }));

  expect(await screen.findByText("CMP-2026-000042")).toBeInTheDocument();
  const sent = vi.mocked(complaintService.createComplaint).mock.calls[0][0];
  expect(sent).toMatchObject({ category_id: 3, location_text: "Ameerpet, Hyderabad", latitude: null });
  expect(sent.attachments.map((f) => f.name)).toEqual(["drain.png"]);
  expect(sent.incident_at).toMatch(/Z$/);
  expect(screen.getByRole("link", { name: "View complaint" })).toHaveAttribute("href", "/app/complaints/42");
});

test("uses the AI-suggested category only when clicked and reports that it was accepted", async () => {
  vi.mocked(aiService.analyzeComplaint).mockResolvedValue({
    model_status: "ready",
    category: { id: 3, name: CATEGORY.name, slug: CATEGORY.slug, confidence: 0.91 },
    alternatives: [],
    department: CATEGORY.department,
    priority: { level: "medium", factors: [] },
    sentiment: { label: "negative", score: -0.3, urgency: 0 },
    possible_emergency: false,
    emergency_message: null,
    duplicates: [],
    model_version: "test",
    disclaimer: "Synthetic data.",
  } as AnalyzeResult);
  vi.mocked(complaintService.createComplaint).mockResolvedValue({
    id: 43,
    reference_number: "CMP-2026-000043",
    department: CATEGORY.department,
  } as ComplaintDetail);
  renderPage();
  await screen.findByRole("option", { name: CATEGORY.name });
  fireEvent.change(screen.getByLabelText("Subject"), { target: { value: "Drain overflowing near bus stop" } });
  fireEvent.change(screen.getByLabelText("Description"), {
    target: { value: "Dirty water has been overflowing onto the road for three days." },
  });
  fireEvent.change(screen.getByLabelText("Address or nearest landmark"), { target: { value: "Ameerpet, Hyderabad" } });

  fireEvent.click(screen.getByRole("button", { name: "Analyse with AI" }));
  fireEvent.click(await screen.findByRole("button", { name: "Use this category" }));
  expect(screen.getByLabelText("Category")).toHaveValue("3");

  fireEvent.click(screen.getByRole("button", { name: "Submit complaint" }));
  expect(await screen.findByText("CMP-2026-000043")).toBeInTheDocument();
  expect(vi.mocked(complaintService.createComplaint).mock.calls[0][0]).toMatchObject({
    category_id: 3,
    ai_category_accepted: true,
  });
});

test("preselects the category from the ?category= query parameter", async () => {
  render(
    <MemoryRouter initialEntries={["/app/complaints/new?category=3"]}>
      <NewComplaintPage />
    </MemoryRouter>,
  );
  await screen.findByRole("option", { name: CATEGORY.name });
  expect(screen.getByLabelText("Category")).toHaveValue("3");
});

test("ignores an unknown ?category= value", async () => {
  render(
    <MemoryRouter initialEntries={["/app/complaints/new?category=999"]}>
      <NewComplaintPage />
    </MemoryRouter>,
  );
  await screen.findByRole("option", { name: CATEGORY.name });
  expect(screen.getByLabelText("Category")).toHaveValue("");
});
