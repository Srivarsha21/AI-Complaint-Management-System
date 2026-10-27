/**
 * Instant, client-side emergency keyword check. It runs on every keystroke so the 112 guidance
 * appears immediately, without waiting for the server or any model. Mirrors (a subset of) the
 * backend list in backend/app/ai/priority.py. A match is a prompt, never a verified emergency.
 */
const EMERGENCY_PHRASES = [
  "live wire",
  "hanging wire",
  "wire snapped",
  "fallen wire",
  "electric shock",
  "electrocuted",
  "electrocution",
  "sparking",
  "gas leak",
  "gas leakage",
  "cylinder blast",
  "open manhole",
  "manhole open",
  "fire",
  "caught fire",
  "flames",
  "collapse",
  "collapsed",
  "caved in",
  "trapped",
  "stranded",
  "drowning",
  "swept away",
  "flooding",
  "unconscious",
  "bleeding",
];

export function detectEmergencyKeywords(text: string): string[] {
  const normalised = ` ${text.toLowerCase().replace(/[^a-z0-9\s]/g, " ").replace(/\s+/g, " ").trim()} `;
  return EMERGENCY_PHRASES.filter((phrase) => normalised.includes(` ${phrase} `));
}
