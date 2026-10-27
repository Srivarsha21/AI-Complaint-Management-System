import { fireEvent, render, screen } from "@testing-library/react";
import { vi } from "vitest";

import SpeakButton from "./SpeakButton";

class FakeUtterance {
  text: string;
  lang = "";
  voice: SpeechSynthesisVoice | null = null;
  onend: (() => void) | null = null;
  onerror: (() => void) | null = null;
  constructor(text: string) {
    this.text = text;
  }
}

function installSynth(voices: Array<Partial<SpeechSynthesisVoice>>) {
  const synth = {
    getVoices: vi.fn(() => voices as SpeechSynthesisVoice[]),
    speak: vi.fn(),
    cancel: vi.fn(),
    addEventListener: vi.fn(),
    removeEventListener: vi.fn(),
  };
  Object.defineProperty(window, "speechSynthesis", { value: synth, configurable: true });
  vi.stubGlobal("SpeechSynthesisUtterance", FakeUtterance);
  return synth;
}

afterEach(() => {
  // @ts-expect-error - removing the test double
  delete window.speechSynthesis;
  vi.unstubAllGlobals();
});

test("explains when no Telugu voice is installed and does not speak", () => {
  const synth = installSynth([]);
  render(<SpeakButton text="మా వీధిలో నీళ్ళు రావడం లేదు" />);
  fireEvent.click(screen.getByRole("button", { name: /read aloud/i }));
  expect(screen.getByText(/No Telugu voice is installed on this device/)).toBeInTheDocument();
  expect(synth.speak).not.toHaveBeenCalled();
});

test("reads English text even without a matching voice list, and can stop", () => {
  const synth = installSynth([]);
  render(<SpeakButton text="Drain overflowing. Status: Submitted." />);
  fireEvent.click(screen.getByRole("button", { name: /read aloud/i }));
  expect(synth.speak).toHaveBeenCalledTimes(1);
  const utterance = synth.speak.mock.calls[0][0] as FakeUtterance;
  expect(utterance.lang).toBe("en-IN");

  fireEvent.click(screen.getByRole("button", { name: /stop reading/i }));
  expect(synth.cancel).toHaveBeenCalled();
});

test("picks an installed Telugu voice for Telugu text", () => {
  const telugu = { lang: "te-IN", name: "Telugu" };
  const synth = installSynth([{ lang: "en-US", name: "English" }, telugu]);
  render(<SpeakButton text="నీళ్ళు" />);
  fireEvent.click(screen.getByRole("button", { name: /read aloud/i }));
  expect((synth.speak.mock.calls[0][0] as FakeUtterance).voice).toBe(telugu);
});

test("says so when the browser has no speech synthesis", () => {
  render(<SpeakButton text="hello" />);
  expect(screen.getByText(/not supported in this browser/)).toBeInTheDocument();
});
