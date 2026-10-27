import { useState } from "react";

import { getErrorMessage } from "../../services/api";
import type { ImageAnalysis } from "../../types/ai";
import Button from "../ui/Button";

/** Quality warnings, COCO detections, category hints and the model disclaimer. */
export default function ImageAnalysisResult({ result }: { result: ImageAnalysis }) {
  const warnings: string[] = [];
  if (result.is_blurry) warnings.push("The photo looks blurry. A sharper photo helps staff understand the problem.");
  if (result.too_dark) warnings.push("The photo is very dark. Try taking it in better light.");
  if (result.too_bright) warnings.push("The photo is overexposed (very bright).");

  return (
    <div className="space-y-2 rounded-lg border border-slate-200 bg-slate-50 p-3 text-xs text-slate-700">
      <p className="text-slate-500">
        {result.width} × {result.height} px · sharpness {Math.round(result.blur_score)} · brightness{" "}
        {Math.round(result.brightness)}/255
      </p>
      {warnings.length > 0 ? (
        <ul className="space-y-1">
          {warnings.map((w) => (
            <li key={w} className="text-amber-700">
              ⚠ {w}
            </li>
          ))}
        </ul>
      ) : (
        <p className="text-emerald-700">Photo quality looks fine.</p>
      )}

      {result.detector_available ? (
        <div>
          <p className="font-medium text-slate-800">Objects recognised ({result.model}):</p>
          {result.detections.length === 0 ? (
            <p>None of the model's known object types were found.</p>
          ) : (
            <ul className="mt-1 flex flex-wrap gap-1">
              {result.detections.map((d, i) => (
                <li key={`${d.label}-${i}`} className="rounded bg-white px-1.5 py-0.5 ring-1 ring-slate-200">
                  {d.label} {Math.round(d.confidence * 100)}%
                </li>
              ))}
            </ul>
          )}
        </div>
      ) : (
        <p className="text-slate-500">Object detection is unavailable right now; only photo quality was checked.</p>
      )}

      {result.category_hints.length > 0 && (
        <div>
          <p className="font-medium text-slate-800">Hints (not applied automatically):</p>
          <ul className="mt-1 list-disc space-y-0.5 pl-4">
            {result.category_hints.map((h) => (
              <li key={h.slug}>{h.reason}</li>
            ))}
          </ul>
        </div>
      )}

      <p className="italic text-slate-500">{result.disclaimer}</p>
    </div>
  );
}

interface AnalysisToggleProps {
  name: string;
  load: () => Promise<ImageAnalysis>;
  buttonLabel?: string;
}

/** A per-photo button that loads the analysis on demand and shows/hides it. */
export function ImageAnalysisToggle({ name, load, buttonLabel = "Analyse photo" }: AnalysisToggleProps) {
  const [result, setResult] = useState<ImageAnalysis | null>(null);
  const [open, setOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function toggle() {
    if (open) {
      setOpen(false);
      return;
    }
    setOpen(true);
    if (result) return;
    setLoading(true);
    setError(null);
    try {
      setResult(await load());
    } catch (err) {
      setError(getErrorMessage(err));
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="space-y-2">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <span className="min-w-0 truncate text-sm text-slate-700">{name}</span>
        <Button variant="ghost" onClick={() => void toggle()} aria-expanded={open} disabled={loading}>
          {loading ? "Analysing…" : open ? "Hide analysis" : buttonLabel}
        </Button>
      </div>
      {open && error && (
        <p role="alert" className="text-xs text-red-600">
          {error}
        </p>
      )}
      {open && result && <ImageAnalysisResult result={result} />}
    </div>
  );
}
