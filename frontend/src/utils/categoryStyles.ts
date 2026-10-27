import type { Accent } from "../components/ui/Card";

/** Visual identity per category slug (icon + colour). Unknown slugs fall back to a neutral style. */
export interface CategoryStyle {
  icon: string;
  accent: Accent;
  /** Tailwind classes for a small coloured chip. */
  chip: string;
}

const STYLES: Record<string, CategoryStyle> = {
  "drainage-sewerage": { icon: "🚰", accent: "sky", chip: "bg-sky-50 text-sky-700 ring-sky-200" },
  "garbage-sanitation": { icon: "🗑️", accent: "emerald", chip: "bg-emerald-50 text-emerald-700 ring-emerald-200" },
  "roads-potholes": { icon: "🛣️", accent: "amber", chip: "bg-amber-50 text-amber-800 ring-amber-200" },
  "street-lights": { icon: "💡", accent: "amber", chip: "bg-yellow-50 text-yellow-800 ring-yellow-200" },
  "water-supply": { icon: "💧", accent: "sky", chip: "bg-cyan-50 text-cyan-700 ring-cyan-200" },
  electricity: { icon: "⚡", accent: "violet", chip: "bg-violet-50 text-violet-700 ring-violet-200" },
  "stray-animals": { icon: "🐕", accent: "rose", chip: "bg-orange-50 text-orange-700 ring-orange-200" },
  encroachment: { icon: "🏗️", accent: "slate", chip: "bg-stone-100 text-stone-700 ring-stone-200" },
  "public-health": { icon: "🦟", accent: "rose", chip: "bg-rose-50 text-rose-700 ring-rose-200" },
  pollution: { icon: "🌫️", accent: "slate", chip: "bg-slate-100 text-slate-700 ring-slate-200" },
  "parks-trees": { icon: "🌳", accent: "teal", chip: "bg-teal-50 text-teal-700 ring-teal-200" },
  other: { icon: "📝", accent: "brand", chip: "bg-brand-50 text-brand-700 ring-brand-200" },
};

const FALLBACK: CategoryStyle = { icon: "📌", accent: "brand", chip: "bg-brand-50 text-brand-700 ring-brand-200" };

export function categoryStyle(slug: string | null | undefined): CategoryStyle {
  return (slug && STYLES[slug]) || FALLBACK;
}

/** Lookup by display name, for lists that only carry {id, name}. */
const BY_NAME: Record<string, string> = {
  "Drainage & Sewerage": "drainage-sewerage",
  "Garbage & Sanitation": "garbage-sanitation",
  "Roads & Potholes": "roads-potholes",
  "Street Lights": "street-lights",
  "Water Supply": "water-supply",
  Electricity: "electricity",
  "Stray Animals": "stray-animals",
  "Encroachment & Illegal Construction": "encroachment",
  "Mosquito & Public Health": "public-health",
  "Noise & Air Pollution": "pollution",
  "Parks & Trees": "parks-trees",
  Other: "other",
};

export function categoryStyleByName(name: string | null | undefined): CategoryStyle {
  return categoryStyle(name ? BY_NAME[name] : null);
}
