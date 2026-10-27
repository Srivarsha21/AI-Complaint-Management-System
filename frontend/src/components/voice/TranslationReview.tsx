import { useEffect, useState } from "react";

import { getErrorMessage } from "../../services/api";
import { translateText } from "../../services/aiService";
import { containsTelugu } from "../../utils/language";
import Button from "../ui/Button";

export const TRANSLATION_MARKER = "[English translation]";

/** The user's own text, without a previously appended translation. */
export function originalPart(text: string): string {
  const index = text.indexOf(TRANSLATION_MARKER);
  return (index >= 0 ? text.slice(0, index) : text).trim();
}

interface TranslationReviewProps {
  text: string;
  /** Called with the text to append below the original (marker included). */
  onAppend: (block: string) => void;
}

/**
 * Shown when the description contains Telugu. The translation is displayed separately for
 * review; the original description is never replaced.
 */
export default function TranslationReview({ text, onAppend }: TranslationReviewProps) {
  const original = originalPart(text);
  const [translation, setTranslation] = useState<string | null>(null);
  const [translatedFrom, setTranslatedFrom] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const alreadyAppended = text.includes(TRANSLATION_MARKER);

  // A translation of older text must not be appended to newer text.
  useEffect(() => {
    if (translatedFrom !== null && translatedFrom !== original) {
      setTranslation(null);
      setTranslatedFrom(null);
    }
  }, [original, translatedFrom]);

  if (!containsTelugu(original)) return null;

  async function translate() {
    setLoading(true);
    setError(null);
    try {
      const result = await translateText(original, "en", "te");
      setTranslation(result.translated_text);
      setTranslatedFrom(original);
    } catch (err) {
      setError(getErrorMessage(err));
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="space-y-2 rounded-lg border border-slate-200 bg-white p-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <p className="text-xs text-slate-600">
          Your description is in Telugu. It will be submitted exactly as you wrote it.
        </p>
        <Button variant="secondary" onClick={() => void translate()} disabled={loading}>
          {loading ? "Translating…" : "Translate to English for review"}
        </Button>
      </div>
      {error && (
        <p role="alert" className="text-xs text-red-600">
          {error}
        </p>
      )}
      {translation !== null && (
        <div className="space-y-2">
          <label htmlFor="translation-preview" className="block text-xs font-medium text-slate-700">
            Machine translation (read-only, may contain mistakes)
          </label>
          <textarea
            id="translation-preview"
            readOnly
            rows={4}
            value={translation}
            className="block w-full rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-sm text-slate-700"
          />
          {alreadyAppended ? (
            <p className="text-xs text-slate-500">An English translation is already appended to the description.</p>
          ) : (
            <Button variant="ghost" onClick={() => onAppend(`${TRANSLATION_MARKER}\n${translation}`)}>
              Append English translation below the original
            </Button>
          )}
        </div>
      )}
    </div>
  );
}
