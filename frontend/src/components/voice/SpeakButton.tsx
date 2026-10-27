import { useEffect, useState } from "react";

import { containsTelugu } from "../../utils/language";
import Button from "../ui/Button";

const NO_TELUGU_VOICE =
  "No Telugu voice is installed on this device, so this text cannot be read aloud. You can add a Telugu voice in your operating system's speech or language settings.";

function pickVoice(voices: SpeechSynthesisVoice[], telugu: boolean): SpeechSynthesisVoice | null {
  const lang = (v: SpeechSynthesisVoice) => v.lang.toLowerCase().replace("_", "-");
  if (telugu) return voices.find((v) => lang(v).startsWith("te")) ?? null;
  return voices.find((v) => lang(v) === "en-in") ?? voices.find((v) => lang(v).startsWith("en")) ?? null;
}

/** Optional accessibility aid: reads `text` aloud with the browser's built-in speech synthesis. */
export default function SpeakButton({ text, label = "Read aloud" }: { text: string; label?: string }) {
  const synth = typeof window !== "undefined" && "speechSynthesis" in window ? window.speechSynthesis : null;
  const [voices, setVoices] = useState<SpeechSynthesisVoice[]>(() => synth?.getVoices() ?? []);
  const [speaking, setSpeaking] = useState(false);
  const [message, setMessage] = useState<string | null>(null);

  useEffect(() => {
    if (!synth) return;
    // Voices load asynchronously in Chrome.
    const update = () => setVoices(synth.getVoices());
    synth.addEventListener?.("voiceschanged", update);
    return () => {
      synth.removeEventListener?.("voiceschanged", update);
      synth.cancel();
    };
  }, [synth]);

  if (!synth || typeof SpeechSynthesisUtterance === "undefined") {
    return <p className="text-xs text-slate-500">Read-aloud is not supported in this browser.</p>;
  }

  function speak() {
    if (!synth) return;
    setMessage(null);
    const telugu = containsTelugu(text);
    const voice = pickVoice(voices.length ? voices : synth.getVoices(), telugu);
    if (telugu && !voice) {
      setMessage(NO_TELUGU_VOICE);
      return;
    }
    synth.cancel();
    const utterance = new SpeechSynthesisUtterance(text);
    utterance.lang = telugu ? "te-IN" : "en-IN";
    if (voice) utterance.voice = voice;
    utterance.onend = () => setSpeaking(false);
    utterance.onerror = () => setSpeaking(false);
    setSpeaking(true);
    synth.speak(utterance);
  }

  function stop() {
    synth?.cancel();
    setSpeaking(false);
  }

  return (
    <div className="space-y-1">
      {speaking ? (
        <Button variant="secondary" onClick={stop}>
          ■ Stop reading
        </Button>
      ) : (
        <Button variant="secondary" onClick={speak} disabled={!text.trim()}>
          🔊 {label}
        </Button>
      )}
      {message && (
        <p role="status" className="max-w-xs text-xs text-amber-700">
          {message}
        </p>
      )}
    </div>
  );
}
