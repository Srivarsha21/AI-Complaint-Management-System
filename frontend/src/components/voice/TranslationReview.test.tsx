import { fireEvent, render, screen } from "@testing-library/react";
import { AxiosError, AxiosHeaders } from "axios";
import { useState } from "react";
import { vi } from "vitest";

import * as aiService from "../../services/aiService";
import { appendText } from "../../utils/language";
import TranslationReview from "./TranslationReview";

vi.mock("../../services/aiService");

const TELUGU = "మా వీధిలో మూడు రోజులుగా నీళ్ళు రావడం లేదు";
const UNAVAILABLE = "Translation is unavailable right now; your complaint will be submitted in the original language.";

function Harness({ initial }: { initial: string }) {
  const [text, setText] = useState(initial);
  return (
    <>
      <p data-testid="description">{text}</p>
      <TranslationReview text={text} onAppend={(block) => setText((d) => appendText(d, block, 5000, "\n\n"))} />
    </>
  );
}

function axios503() {
  const headers = new AxiosHeaders();
  return new AxiosError("Service Unavailable", "ERR_BAD_RESPONSE", { headers }, null, {
    status: 503,
    statusText: "Service Unavailable",
    data: { detail: UNAVAILABLE },
    headers: {},
    config: { headers },
  });
}

afterEach(() => vi.resetAllMocks());

test("is hidden for English text", () => {
  render(<Harness initial="No water for three days" />);
  expect(screen.queryByRole("button", { name: /translate/i })).not.toBeInTheDocument();
});

test("shows the 503 fallback message and keeps the original text", async () => {
  vi.mocked(aiService.translateText).mockRejectedValue(axios503());
  render(<Harness initial={TELUGU} />);
  fireEvent.click(screen.getByRole("button", { name: "Translate to English for review" }));
  expect(await screen.findByRole("alert")).toHaveTextContent(UNAVAILABLE);
  expect(screen.getByTestId("description")).toHaveTextContent(TELUGU);
});

test("shows the translation separately and appends it only on request, clearly marked", async () => {
  vi.mocked(aiService.translateText).mockResolvedValue({
    translated_text: "No water has come in our street for three days",
    source_language: "te",
    target_language: "en",
    provider: "gemini",
  });
  render(<Harness initial={TELUGU} />);
  fireEvent.click(screen.getByRole("button", { name: "Translate to English for review" }));

  const preview = await screen.findByLabelText(/Machine translation/);
  expect(preview).toHaveValue("No water has come in our street for three days");
  expect(preview).toHaveAttribute("readonly");
  expect(aiService.translateText).toHaveBeenCalledWith(TELUGU, "en", "te");
  expect(screen.getByTestId("description").textContent).toBe(TELUGU);

  fireEvent.click(screen.getByRole("button", { name: /Append English translation/ }));
  expect(screen.getByTestId("description").textContent).toBe(
    `${TELUGU}\n\n[English translation]\nNo water has come in our street for three days`,
  );
  expect(screen.queryByRole("button", { name: /Append English translation/ })).not.toBeInTheDocument();
});
