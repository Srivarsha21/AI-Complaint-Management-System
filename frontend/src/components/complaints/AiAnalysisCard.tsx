import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { getErrorMessage } from "../../services/api";
import { getComplaintAi } from "../../services/aiService";
import type { ComplaintAiAnalysis } from "../../types/ai";
import { PRIORITY_LABELS, STATUS_LABELS } from "../../utils/complaintLabels";
import Card from "../ui/Card";
import Spinner from "../ui/Spinner";

const percent = (value: number) => `${Math.round(value * 100)}%`;

/** Staff-only card: what the AI predicted at submission, plus similar open complaints. */
export default function AiAnalysisCard({ complaintId, refreshKey }: { complaintId: number; refreshKey?: unknown }) {
  const [analysis, setAnalysis] = useState<ComplaintAiAnalysis | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let active = true;
    setLoading(true);
    getComplaintAi(complaintId)
      .then((data) => active && setAnalysis(data))
      .catch((err) => active && setError(getErrorMessage(err)))
      .finally(() => active && setLoading(false));
    return () => {
      active = false;
    };
  }, [complaintId, refreshKey]);

  return (
    <Card title="AI analysis" description="Predictions to help triage. They can be wrong; staff decide.">
      {loading ? (
        <Spinner label="Loading AI analysis" />
      ) : error ? (
        <p className="text-sm text-red-600">{error}</p>
      ) : analysis ? (
        <div className="space-y-4 text-sm">
          {analysis.prediction ? (
            <dl className="space-y-2">
              <div>
                <dt className="text-xs font-medium uppercase tracking-wide text-slate-500">Predicted category</dt>
                <dd>
                  {analysis.prediction.predicted_category
                    ? `${analysis.prediction.predicted_category.name} (${percent(analysis.prediction.predicted_category.confidence)} confidence)`
                    : analysis.model_status === "not_trained"
                      ? "Model not trained"
                      : "No prediction"}
                  {analysis.prediction.user_accepted_category != null && (
                    <span className="ml-1 text-xs text-slate-500">
                      · citizen {analysis.prediction.user_accepted_category ? "kept" : "did not keep"} the suggestion
                    </span>
                  )}
                </dd>
              </div>
              <div>
                <dt className="text-xs font-medium uppercase tracking-wide text-slate-500">Predicted priority</dt>
                <dd>
                  {analysis.prediction.predicted_priority ? PRIORITY_LABELS[analysis.prediction.predicted_priority] : "—"}
                  {analysis.prediction.possible_emergency && (
                    <span className="ml-2 rounded bg-red-100 px-1.5 py-0.5 text-xs font-medium text-red-800">
                      Emergency keywords (unverified)
                    </span>
                  )}
                  {analysis.prediction.priority_factors.length > 0 && (
                    <ul className="mt-1 list-disc pl-5 text-xs text-slate-600">
                      {analysis.prediction.priority_factors.map((f) => (
                        <li key={f}>{f}</li>
                      ))}
                    </ul>
                  )}
                </dd>
              </div>
              <div>
                <dt className="text-xs font-medium uppercase tracking-wide text-slate-500">Sentiment</dt>
                <dd>
                  {analysis.prediction.sentiment_label ?? "—"}
                  {analysis.prediction.sentiment_score != null && ` (score ${analysis.prediction.sentiment_score.toFixed(2)}`}
                  {analysis.prediction.urgency_score != null && `, urgency ${analysis.prediction.urgency_score.toFixed(2)})`}
                </dd>
              </div>
            </dl>
          ) : (
            <p className="text-slate-500">No AI prediction was stored for this complaint.</p>
          )}

          <section>
            <h3 className="font-medium text-slate-900">Similar open complaints</h3>
            {analysis.similar.length === 0 ? (
              <p className="mt-1 text-xs text-slate-500">None found in the same category recently.</p>
            ) : (
              <ul className="mt-1 space-y-1">
                {analysis.similar.map((s) => (
                  <li key={s.complaint_id ?? s.reference_number} className="text-xs">
                    {s.complaint_id ? (
                      <Link to={`/app/complaints/${s.complaint_id}`} className="font-mono text-brand-600 hover:underline">
                        {s.reference_number}
                      </Link>
                    ) : (
                      <span className="font-mono">{s.reference_number}</span>
                    )}{" "}
                    {s.subject && <span className="text-slate-700">{s.subject}</span>} ·{" "}
                    {STATUS_LABELS[s.status]} · {percent(s.similarity)} similar
                    {s.distance_m != null && ` · ${Math.round(s.distance_m)} m away`}
                  </li>
                ))}
              </ul>
            )}
          </section>

          <p className="text-xs text-slate-400">
            {analysis.prediction?.model_version ? `Model ${analysis.prediction.model_version}. ` : ""}
            {analysis.disclaimer}
          </p>
        </div>
      ) : null}
    </Card>
  );
}
