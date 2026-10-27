/**
 * Unicode-range language detection for English / Telugu (mirrors backend app/ai/language.py).
 * Telugu script is the block U+0C00–U+0C7F. This checks the script, not the language:
 * romanised Telugu ("naaku neellu raavatledu") counts as English script.
 */
export type DetectedLanguage = "te" | "en" | "unknown";

const TELUGU_RATIO = 0.3;

export function isTeluguChar(ch: string): boolean {
  const code = ch.codePointAt(0) ?? 0;
  return code >= 0x0c00 && code <= 0x0c7f;
}

export function containsTelugu(text: string): boolean {
  return /[ఀ-౿]/.test(text);
}

export function detectLanguage(text: string): DetectedLanguage {
  let telugu = 0;
  let latin = 0;
  for (const ch of text) {
    if (isTeluguChar(ch)) telugu += 1;
    else if (/[A-Za-z]/.test(ch)) latin += 1;
  }
  const letters = telugu + latin;
  if (letters === 0) return "unknown";
  if (telugu / letters >= TELUGU_RATIO) return "te";
  return latin > 0 ? "en" : "unknown";
}

/** Appends `addition` to `text` on a new line (or with a space), never exceeding `max` characters. */
export function appendText(text: string, addition: string, max: number, separator = " "): string {
  const clean = addition.trim();
  if (!clean) return text;
  const joined = text.trim() ? `${text.replace(/\s+$/, "")}${separator}${clean}` : clean;
  return joined.slice(0, max);
}
