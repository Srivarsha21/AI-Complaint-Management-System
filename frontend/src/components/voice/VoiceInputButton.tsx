import { useEffect, useId, useRef, useState } from "react";

import { getSpeechRecognition, type SpeechRecognitionLike } from "../../types/speech";
import Button from "../ui/Button";

export const VOICE_LANGUAGES = [
  { code: "en-IN", label: "English (India)" },
  { code: "te-IN", label: "తెలుగు (Telugu)" },
] as const;

export type VoiceLanguage = (typeof VOICE_LANGUAGES)[number]["code"];

const UNSUPPORTED =
  "Voice input is not supported in this browser (for example Firefox). Please type your complaint, or use Chrome or Edge.";

function errorMessage(code: string): string {
  switch (code) {
    case "not-allowed":
    case "service-not-allowed":
      return "Microphone access was blocked. Allow the microphone for this site in your browser settings, or type instead.";
    case "audio-capture":
      return "No microphone was found. Check that one is connected, or type instead.";
    case "no-speech":
      return "No speech was heard. Please try again and speak clearly.";
    case "network":
      return "The browser's speech service could not be reached. Check your connection, or type instead.";
    case "language-not-supported":
      return "This browser cannot recognise the selected language. Try English, or type instead.";
    default:
      return "Voice input stopped because of an error. You can try again or type instead.";
  }
}

interface VoiceInputButtonProps {
  /** Called with each finalised phrase; the caller appends it to an editable field. */
  onTranscript: (text: string) => void;
  disabled?: boolean;
}

/**
 * Dictation via the browser's Web Speech API. Recognised text is only ever appended to a
 * field the user can edit before submitting; nothing is sent to this application's server.
 */
export default function VoiceInputButton({ onTranscript, disabled = false }: VoiceInputButtonProps) {
  const Recognition = getSpeechRecognition();
  const selectId = useId();
  const [language, setLanguage] = useState<VoiceLanguage>("en-IN");
  const [listening, setListening] = useState(false);
  const [interim, setInterim] = useState("");
  const [error, setError] = useState<string | null>(null);
  const recognitionRef = useRef<SpeechRecognitionLike | null>(null);
  const onTranscriptRef = useRef(onTranscript);
  onTranscriptRef.current = onTranscript;

  useEffect(() => () => recognitionRef.current?.abort(), []);

  if (!Recognition) {
    return <p className="text-xs text-slate-500">{UNSUPPORTED}</p>;
  }

  function start() {
    if (!Recognition) return;
    setError(null);
    setInterim("");
    const recognition = new Recognition();
    recognition.lang = language;
    recognition.continuous = true;
    recognition.interimResults = true;
    recognition.maxAlternatives = 1;
    recognition.onresult = (event) => {
      let pending = "";
      for (let i = event.resultIndex; i < event.results.length; i += 1) {
        const result = event.results[i];
        const text = result[0]?.transcript ?? "";
        if (result.isFinal) {
          if (text.trim()) onTranscriptRef.current(text.trim());
        } else {
          pending += text;
        }
      }
      setInterim(pending);
    };
    recognition.onerror = (event) => {
      // "aborted" happens when we stop it ourselves.
      if (event.error !== "aborted") setError(errorMessage(event.error));
    };
    recognition.onend = () => {
      setListening(false);
      setInterim("");
      recognitionRef.current = null;
    };
    recognitionRef.current = recognition;
    try {
      recognition.start();
      setListening(true);
    } catch {
      recognitionRef.current = null;
      setError(errorMessage("start-failed"));
    }
  }

  function stop() {
    recognitionRef.current?.stop();
  }

  return (
    <div className="space-y-2 rounded-lg border border-slate-200 bg-slate-50 p-3">
      <div className="flex flex-wrap items-center gap-2">
        <label htmlFor={selectId} className="text-xs font-medium text-slate-600">
          Speak in
        </label>
        <select
          id={selectId}
          value={language}
          onChange={(e) => setLanguage(e.target.value as VoiceLanguage)}
          disabled={listening}
          className="rounded-lg border border-slate-300 bg-white px-2 py-1 text-sm"
        >
          {VOICE_LANGUAGES.map((l) => (
            <option key={l.code} value={l.code}>
              {l.label}
            </option>
          ))}
        </select>
        {listening ? (
          <Button variant="secondary" onClick={stop} aria-label="Stop voice input">
            <span className="h-2 w-2 animate-pulse rounded-full bg-red-600" aria-hidden /> Stop
          </Button>
        ) : (
          <Button variant="secondary" onClick={start} disabled={disabled}>
            🎤 Speak description
          </Button>
        )}
      </div>
      <p className="text-xs text-slate-500">
        Privacy: voice input uses your browser's speech service. In Chrome and Edge, your audio is sent to the browser
        maker's servers (for example Google) to be turned into text. The text is added to the description so you can
        check and correct it before submitting.
      </p>
      {listening && (
        <p className="text-sm text-slate-700" aria-live="polite">
          <span className="font-medium text-red-700">Listening…</span> {interim && <em className="text-slate-500">{interim}</em>}
        </p>
      )}
      {error && (
        <p role="alert" className="text-xs text-red-600">
          {error}
        </p>
      )}
    </div>
  );
}
