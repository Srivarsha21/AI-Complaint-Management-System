import { act, fireEvent, render, screen } from "@testing-library/react";
import { useState } from "react";
import { vi } from "vitest";

import type { SpeechRecognitionEventLike, SpeechRecognitionLike } from "../../types/speech";
import { appendText } from "../../utils/language";
import VoiceInputButton from "./VoiceInputButton";

class MockRecognition implements SpeechRecognitionLike {
  static last: MockRecognition | null = null;
  lang = "";
  continuous = false;
  interimResults = false;
  maxAlternatives = 1;
  onresult: SpeechRecognitionLike["onresult"] = null;
  onerror: SpeechRecognitionLike["onerror"] = null;
  onend: SpeechRecognitionLike["onend"] = null;
  onstart: SpeechRecognitionLike["onstart"] = null;
  start = vi.fn();
  stop = vi.fn(() => this.onend?.());
  abort = vi.fn();
  constructor() {
    MockRecognition.last = this;
  }
}

function speechEvent(parts: Array<{ text: string; isFinal: boolean }>): SpeechRecognitionEventLike {
  const results = parts.map((p) => Object.assign([{ transcript: p.text, confidence: 0.9 }], { isFinal: p.isFinal }));
  return { resultIndex: 0, results } as unknown as SpeechRecognitionEventLike;
}

function Harness({ initial = "" }: { initial?: string }) {
  const [text, setText] = useState(initial);
  return (
    <>
      <label htmlFor="desc">Description</label>
      <textarea id="desc" value={text} onChange={(e) => setText(e.target.value)} />
      <VoiceInputButton onTranscript={(t) => setText((d) => appendText(d, t, 5000))} />
    </>
  );
}

afterEach(() => {
  delete window.SpeechRecognition;
  delete window.webkitSpeechRecognition;
  MockRecognition.last = null;
});

test("shows a clear fallback when the browser has no speech recognition", () => {
  render(<Harness />);
  expect(screen.getByText(/not supported in this browser/)).toBeInTheDocument();
  expect(screen.queryByRole("button", { name: /speak/i })).not.toBeInTheDocument();
});

test("discloses that audio goes to the browser's speech service", () => {
  window.webkitSpeechRecognition = MockRecognition;
  render(<Harness />);
  expect(screen.getByText(/your audio is sent to the browser maker's servers/)).toBeInTheDocument();
});

test("uses the chosen language, shows interim text and appends the final transcript", () => {
  window.webkitSpeechRecognition = MockRecognition;
  render(<Harness initial="Drain blocked." />);

  fireEvent.change(screen.getByLabelText("Speak in"), { target: { value: "te-IN" } });
  fireEvent.click(screen.getByRole("button", { name: /speak description/i }));
  const recognition = MockRecognition.last!;
  expect(recognition.start).toHaveBeenCalled();
  expect(recognition.lang).toBe("te-IN");
  expect(recognition.interimResults).toBe(true);

  act(() => recognition.onresult?.(speechEvent([{ text: "నీళ్ళు రావడం", isFinal: false }])));
  expect(screen.getByText("నీళ్ళు రావడం")).toBeInTheDocument();

  act(() => recognition.onresult?.(speechEvent([{ text: "నీళ్ళు రావడం లేదు", isFinal: true }])));
  expect(screen.getByLabelText("Description")).toHaveValue("Drain blocked. నీళ్ళు రావడం లేదు");

  // The transcript stays editable.
  fireEvent.change(screen.getByLabelText("Description"), { target: { value: "edited" } });
  expect(screen.getByLabelText("Description")).toHaveValue("edited");

  fireEvent.click(screen.getByRole("button", { name: "Stop voice input" }));
  expect(recognition.stop).toHaveBeenCalled();
  expect(screen.getByRole("button", { name: /speak description/i })).toBeInTheDocument();
});

test("explains when microphone permission is denied", () => {
  window.SpeechRecognition = MockRecognition;
  render(<Harness />);
  fireEvent.click(screen.getByRole("button", { name: /speak description/i }));
  act(() => {
    MockRecognition.last!.onerror?.({ error: "not-allowed" });
    MockRecognition.last!.onend?.();
  });
  expect(screen.getByRole("alert")).toHaveTextContent("Microphone access was blocked");
  expect(screen.getByLabelText("Description")).toHaveValue("");
});
