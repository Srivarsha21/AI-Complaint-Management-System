import { useEffect, useRef, useState } from "react";

import { getErrorMessage } from "../../services/api";
import { analyzeComplaint } from "../../services/aiService";
import type { AnalyzeResult, CategorySuggestion } from "../../types/ai";
import { PRIORITY_LABELS, STATUS_LABELS } from "../../utils/complaintLabels";
import { detectEmergencyKeywords } from "../../utils/emergency";
import Button from "../ui/Button";
import Card from "../ui/Card";

const MIN_DESCRIPTION = 10; // backend minimum for /ai/analyze
const AUTO_RUN_MIN = 20;
const AUTO_RUN_DELAY_MS = 1500;
const LOW_CONFIDENCE = 0.5;

interface Props {
  subject: string;
  description: string;
  latitude?: number | null;
  longitude?: number | null;
  /** The category currently chosen in the form, if any. */
  categoryId: number | null;
  /** Called only when the user clicks "Use this category"; the panel never changes the form by itself. */
  onUseCategory: (categoryId: number) => void;
  /** Reports the AI's top suggestion (or null) so the form can record whether it was accepted. */
  onSuggestion?: (categoryId: number | null) => void;
  /** Analyse automatically (debounced) once the description is long enough. */
  autoRun?: boolean;
}

const percent = (value: number) => `${Math.round(value * 100)}%`;

export default function AiSuggestionPanel({
  subject,
  description,
  latitude,
  longitude,
  categoryId,
  onUseCategory,
  onSuggestion,
  autoRun = true,
}: Props) {
  const [result, setResult] = useState<AnalyzeResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const lastAnalysed = useRef<string | null>(null);
  const requestId = useRef(0);

  // Instant keyword check: never waits for the server.
  const localKeywords = detectEmergencyKeywords(`${subject} ${description}`);
  const showEmergency = localKeywords.length > 0 || Boolean(result?.possible_emergency);
  const canAnalyse = description.trim().length >= MIN_DESCRIPTION;

  async function run() {
    if (!canAnalyse) return;
    const key = `${subject.trim()}\n${description.trim()}`;
    lastAnalysed.current = key;
    const id = ++requestId.current;
    setLoading(true);
    setError(null);
    try {
      const data = await analyzeComplaint({
        subject: subject.trim(),
        description: description.trim(),
        latitude: latitude ?? null,
        longitude: longitude ?? null,
        category_id: categoryId,
      });
      if (id !== requestId.current) return; // a newer request is in flight
      setResult(data);
      onSuggestion?.(data.category?.id ?? null);
    } catch (err) {
      if (id === requestId.current) setError(getErrorMessage(err));
    } finally {
      if (id === requestId.current) setLoading(false);
    }
  }

  useEffect(() => {
    if (!autoRun || description.trim().length < AUTO_RUN_MIN) return;
    const key = `${subject.trim()}\n${description.trim()}`;
    if (key === lastAnalysed.current) return;
    const timer = window.setTimeout(() => void run(), AUTO_RUN_DELAY_MS);
    return () => window.clearTimeout(timer);
    // Re-run only when the text changes; category/location are read at call time.
  }, [subject, description, autoRun]);

  return (
    <div className="space-y-4">
      {showEmergency && (
        <div role="alert" className="rounded-lg border-2 border-red-300 bg-red-50 p-4 text-sm text-red-800">
          <p className="font-semibold">This may be an emergency.</p>
          <p className="mt-1">
            If anyone is in danger, call{" "}
            <a href="tel:112" className="font-bold underline">
              112
            </a>{" "}
            now. Filing a complaint here does <strong>not</strong> alert emergency services.
          </p>
          {localKeywords.length > 0 && (
            <p className="mt-1 text-xs text-red-700">Detected words: {localKeywords.join(", ")}</p>
          )}
        </div>
      )}

      <Card title="AI suggestions" description="Optional. Suggestions can be wrong — you decide what to submit.">
        <div className="space-y-4">
          <div className="flex flex-wrap items-center gap-3">
            <Button variant="secondary" onClick={() => void run()} disabled={!canAnalyse || loading}>
              {loading ? "Analysing…" : result ? "Analyse again" : "Analyse with AI"}
            </Button>
            {!canAnalyse && <span className="text-xs text-slate-500">Write a short description first.</span>}
          </div>

          {error && <p className="text-sm text-red-600">AI suggestions are unavailable right now ({error}). You can still submit.</p>}

          {result && (
            <div className="space-y-4 text-sm">
              <section>
                <h3 className="font-medium text-slate-900">Suggested category</h3>
                {result.model_status === "not_trained" ? (
                  <p className="mt-1 text-slate-500">Category suggestions are unavailable (the model has not been trained).</p>
                ) : result.category ? (
                  <div className="mt-1 space-y-2">
                    <SuggestionRow suggestion={result.category} selected={categoryId === result.category.id} onUse={onUseCategory} primary />
                    {result.department && (
                      <p className="text-xs text-slate-500">
                        Would be routed to: <strong>{result.department.name}</strong>
                      </p>
                    )}
                    {result.category.confidence < LOW_CONFIDENCE && (
                      <p className="text-xs text-amber-700">Low confidence — please check the category yourself.</p>
                    )}
                    {result.alternatives.length > 0 && (
                      <div>
                        <p className="text-xs text-slate-500">Other possibilities:</p>
                        <ul className="mt-1 space-y-1">
                          {result.alternatives.map((alt) => (
                            <li key={alt.id}>
                              <SuggestionRow suggestion={alt} selected={categoryId === alt.id} onUse={onUseCategory} />
                            </li>
                          ))}
                        </ul>
                      </div>
                    )}
                  </div>
                ) : (
                  <p className="mt-1 text-slate-500">No suggestion for this text.</p>
                )}
              </section>

              <section>
                <h3 className="font-medium text-slate-900">
                  Predicted priority: <span data-testid="ai-priority">{PRIORITY_LABELS[result.priority.level]}</span>
                </h3>
                <p className="text-xs text-slate-500">AI-predicted, may be reviewed by staff.</p>
                {result.priority.factors.length > 0 && (
                  <ul className="mt-1 list-disc pl-5 text-xs text-slate-600">
                    {result.priority.factors.map((factor) => (
                      <li key={factor}>{factor}</li>
                    ))}
                  </ul>
                )}
              </section>

              {result.duplicates.length > 0 && (
                <section>
                  <h3 className="font-medium text-slate-900">Possibly already reported</h3>
                  <ul className="mt-1 space-y-1">
                    {result.duplicates.map((dup, index) => (
                      <li key={dup.reference_number ?? index} className="flex flex-wrap items-center gap-2 text-xs">
                        <span className="font-mono">{dup.reference_number ?? "Unknown reference"}</span>
                        <span className="rounded bg-slate-100 px-1.5 py-0.5 text-slate-700">{STATUS_LABELS[dup.status]}</span>
                        <span className="text-slate-500">{percent(dup.similarity)} similar</span>
                      </li>
                    ))}
                  </ul>
                  <p className="mt-1 text-xs text-slate-500">
                    Similar complaints exist nearby. Filing yours anyway is fine — staff can link duplicates.
                  </p>
                </section>
              )}

              <p className="text-xs text-slate-400">{result.disclaimer}</p>
            </div>
          )}
        </div>
      </Card>
    </div>
  );
}

function SuggestionRow({
  suggestion,
  selected,
  onUse,
  primary = false,
}: {
  suggestion: CategorySuggestion;
  selected: boolean;
  onUse: (id: number) => void;
  primary?: boolean;
}) {
  return (
    <div className="flex flex-wrap items-center gap-2">
      <span className={primary ? "font-semibold text-slate-900" : "text-slate-700"}>{suggestion.name}</span>
      <span className="text-xs text-slate-500">{percent(suggestion.confidence)} confidence</span>
      {selected ? (
        <span className="text-xs font-medium text-emerald-700">Selected</span>
      ) : (
        <Button
          variant={primary ? "secondary" : "ghost"}
          className="px-2 py-1 text-xs"
          onClick={() => onUse(suggestion.id)}
          aria-label={primary ? undefined : `Use category ${suggestion.name}`}
        >
          {primary ? "Use this category" : "Use"}
        </Button>
      )}
    </div>
  );
}
