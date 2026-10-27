import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { PriorityBadge, StatusBadge } from "../../components/complaints/StatusBadge";
import { StatCard } from "../../components/dashboard/UserStats";
import Alert from "../../components/ui/Alert";
import Button from "../../components/ui/Button";
import Spinner from "../../components/ui/Spinner";
import { getErrorMessage } from "../../services/api";
import { listCategories } from "../../services/complaintService";
import { downloadCorrections, getQualitySummary, listAIReviews, reviewPrediction } from "../../services/feedbackService";
import type { Category } from "../../types/complaint";
import type { AIReviewItem, QualitySummary, ReviewSignal, ReviewStatus } from "../../types/feedback";

const PAGE_SIZE = 15;

const SIGNAL_LABELS: Record<ReviewSignal, { label: string; style: string }> = {
  category_changed: { label: "Category differs", style: "bg-violet-50 text-violet-700 ring-violet-200" },
  suggestion_rejected: { label: "Suggestion rejected", style: "bg-amber-50 text-amber-800 ring-amber-200" },
  priority_overridden: { label: "Priority overridden", style: "bg-sky-50 text-sky-700 ring-sky-200" },
  ai_not_helpful: { label: "Rated not helpful", style: "bg-rose-50 text-rose-700 ring-rose-200" },
};

function percent(value: number | null): string {
  return value === null ? "—" : `${Math.round(value * 100)}%`;
}

export default function AIReviewPage() {
  const [summary, setSummary] = useState<QualitySummary | null>(null);
  const [categories, setCategories] = useState<Category[]>([]);
  const [items, setItems] = useState<AIReviewItem[]>([]);
  const [total, setTotal] = useState(0);
  const [flaggedOnly, setFlaggedOnly] = useState(true);
  const [status, setStatus] = useState<ReviewStatus | "">("unreviewed");
  const [page, setPage] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [list, quality] = await Promise.all([
        listAIReviews({ review_status: status, flagged_only: flaggedOnly, limit: PAGE_SIZE, offset: page * PAGE_SIZE }),
        getQualitySummary(),
      ]);
      setItems(list.items);
      setTotal(list.total);
      setSummary(quality);
    } catch (err) {
      setError(getErrorMessage(err));
    } finally {
      setLoading(false);
    }
  }, [status, flaggedOnly, page]);

  useEffect(() => {
    void load();
  }, [load]);

  useEffect(() => {
    listCategories().then(setCategories).catch(() => setCategories([]));
  }, []);

  async function exportCsv() {
    setError(null);
    try {
      await downloadCorrections();
    } catch (err) {
      setError(getErrorMessage(err));
    }
  }

  const pageCount = Math.max(1, Math.ceil(total / PAGE_SIZE));

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">AI review</h1>
          <p className="mt-1 max-w-2xl text-sm text-slate-500">
            Check AI predictions where people disagreed with them. Reviews are recorded for quality monitoring only: the model is
            never retrained automatically. Export reviewed corrections for a deliberate retraining run.
          </p>
        </div>
        <Button variant="secondary" onClick={() => void exportCsv()}>
          ⬇ Export corrections (CSV)
        </Button>
      </div>

      {summary && (
        <dl className="grid grid-cols-2 gap-3 lg:grid-cols-4">
          <StatCard
            label="Category agreement"
            value={percent(summary.category_agreement_rate)}
            hint={`Suggestion matched the final category · ${summary.with_category_suggestion} suggestions`}
            tone="violet"
            icon="🧠"
          />
          <StatCard
            label="Suggestions accepted"
            value={percent(summary.suggestion_acceptance_rate)}
            hint={`${summary.priority_overrides} priority override${summary.priority_overrides === 1 ? "" : "s"} by staff`}
            tone="sky"
            icon="👍"
          />
          <StatCard
            label="Citizen rating"
            value={summary.average_rating === null ? "—" : `${summary.average_rating.toFixed(1)} ★`}
            hint={`${summary.feedback_count} feedback · ${percent(summary.satisfied_rate)} say resolved`}
            tone="amber"
            icon="⭐"
          />
          <StatCard
            label="Reviewed"
            value={summary.reviewed}
            hint={`${summary.marked_incorrect} marked incorrect · AI helpful ${percent(summary.ai_helpful_rate)}`}
            tone="emerald"
            icon="✅"
          />
        </dl>
      )}
      <p className="text-xs text-slate-400">
        Agreement and acceptance describe how people used the suggestions in this system. They are not a measured model accuracy;
        see docs/ai_evaluation.md for the evaluation on the held-out test data.
      </p>

      <div className="flex flex-wrap items-center gap-3">
        <label className="flex items-center gap-2 text-sm text-slate-600">
          <input
            type="checkbox"
            checked={flaggedOnly}
            onChange={(e) => {
              setPage(0);
              setFlaggedOnly(e.target.checked);
            }}
            className="h-4 w-4 rounded border-slate-300"
          />
          Only predictions with disagreement signals
        </label>
        <label className="flex items-center gap-2 text-sm text-slate-600">
          Review status
          <select
            value={status}
            onChange={(e) => {
              setPage(0);
              setStatus(e.target.value as ReviewStatus | "");
            }}
            className="rounded-lg border border-slate-300 bg-white px-2 py-1 text-sm"
          >
            <option value="">Any</option>
            <option value="unreviewed">Unreviewed</option>
            <option value="correct">Marked correct</option>
            <option value="incorrect">Marked incorrect</option>
          </select>
        </label>
      </div>

      {notice && <Alert tone="success">{notice}</Alert>}
      {error && <Alert tone="error">{error}</Alert>}

      {loading ? (
        <Spinner label="Loading predictions" />
      ) : items.length === 0 ? (
        <div className="rounded-2xl border border-dashed border-slate-300 bg-white/60 p-10 text-center text-sm text-slate-500">
          Nothing to review with these filters. 🎉
        </div>
      ) : (
        <ul className="space-y-3">
          {items.map((item) => (
            <ReviewRow
              key={item.prediction_id}
              item={item}
              categories={categories}
              onReviewed={(updated) => {
                setItems((list) => list.map((i) => (i.prediction_id === updated.prediction_id ? updated : i)));
                setNotice(`${updated.complaint.reference_number} marked ${updated.review_status}.`);
                void getQualitySummary().then(setSummary).catch(() => undefined);
              }}
            />
          ))}
        </ul>
      )}

      <div className="flex items-center justify-between text-sm text-slate-500">
        <span>
          {total} prediction{total === 1 ? "" : "s"} · page {page + 1} of {pageCount}
        </span>
        <div className="flex gap-2">
          <Button variant="secondary" disabled={page === 0 || loading} onClick={() => setPage((p) => p - 1)}>
            Previous
          </Button>
          <Button variant="secondary" disabled={page + 1 >= pageCount || loading} onClick={() => setPage((p) => p + 1)}>
            Next
          </Button>
        </div>
      </div>
    </div>
  );
}

function ReviewRow({
  item,
  categories,
  onReviewed,
}: {
  item: AIReviewItem;
  categories: Category[];
  onReviewed: (item: AIReviewItem) => void;
}) {
  const [corrected, setCorrected] = useState<string>(item.corrected_category ? String(item.corrected_category.id) : "");
  const [note, setNote] = useState(item.review_note ?? "");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function save(reviewStatus: "correct" | "incorrect") {
    setSaving(true);
    setError(null);
    try {
      onReviewed(
        await reviewPrediction(item.prediction_id, {
          review_status: reviewStatus,
          corrected_category_id: reviewStatus === "incorrect" && corrected ? Number(corrected) : null,
          note,
        }),
      );
    } catch (err) {
      setError(getErrorMessage(err));
    } finally {
      setSaving(false);
    }
  }

  const reviewedBadge =
    item.review_status === "unreviewed"
      ? "bg-slate-100 text-slate-600"
      : item.review_status === "correct"
        ? "bg-emerald-100 text-emerald-700"
        : "bg-rose-100 text-rose-700";

  return (
    <li className="rounded-2xl border border-slate-200 bg-white p-4 shadow-[var(--shadow-soft)] animate-fade-up">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div className="min-w-0">
          <Link to={`/app/complaints/${item.complaint.id}`} className="font-mono text-xs text-brand-600 hover:underline">
            {item.complaint.reference_number}
          </Link>
          <p className="truncate font-semibold text-slate-900">{item.complaint.subject}</p>
        </div>
        <div className="flex items-center gap-2">
          <StatusBadge status={item.complaint.status} />
          <span className={`rounded-full px-2 py-0.5 text-xs font-semibold capitalize ${reviewedBadge}`}>{item.review_status}</span>
        </div>
      </div>

      <div className="mt-3 flex flex-wrap gap-1.5">
        {item.signals.map((signal) => (
          <span key={signal} className={`rounded-full px-2 py-0.5 text-xs font-medium ring-1 ${SIGNAL_LABELS[signal].style}`}>
            {SIGNAL_LABELS[signal].label}
          </span>
        ))}
      </div>

      <dl className="mt-3 grid gap-3 text-sm sm:grid-cols-2">
        <div>
          <dt className="text-xs uppercase tracking-wide text-slate-500">Category</dt>
          <dd>
            AI: <strong>{item.predicted_category?.name ?? "no suggestion"}</strong>
            {item.category_confidence !== null && ` (${Math.round(item.category_confidence * 100)}%)`} → final:{" "}
            <strong>{item.final_category.name}</strong>
          </dd>
        </div>
        <div>
          <dt className="text-xs uppercase tracking-wide text-slate-500">Priority</dt>
          <dd className="flex items-center gap-1.5">
            AI: <PriorityBadge priority={item.predicted_priority} /> → now: <PriorityBadge priority={item.final_priority} />
            <span className="text-xs text-slate-400">({item.priority_source ?? "—"})</span>
          </dd>
        </div>
      </dl>

      <div className="mt-4 grid gap-2 sm:grid-cols-[1fr_1fr_auto] sm:items-end">
        <label className="text-sm">
          <span className="text-xs text-slate-500">Correct category (if incorrect)</span>
          <select
            value={corrected}
            onChange={(e) => setCorrected(e.target.value)}
            className="mt-1 block w-full rounded-lg border border-slate-300 bg-white px-2 py-1.5 text-sm"
          >
            <option value="">Use the final category</option>
            {categories.map((c) => (
              <option key={c.id} value={c.id}>
                {c.name}
              </option>
            ))}
          </select>
        </label>
        <label className="text-sm">
          <span className="text-xs text-slate-500">Note</span>
          <input
            value={note}
            maxLength={1000}
            onChange={(e) => setNote(e.target.value)}
            className="mt-1 block w-full rounded-lg border border-slate-300 px-2 py-1.5 text-sm"
          />
        </label>
        <div className="flex gap-2">
          <Button variant="secondary" disabled={saving} onClick={() => void save("correct")}>
            ✓ Correct
          </Button>
          <Button variant="danger" disabled={saving} onClick={() => void save("incorrect")}>
            ✗ Incorrect
          </Button>
        </div>
      </div>
      {error && (
        <div className="mt-2">
          <Alert tone="error">{error}</Alert>
        </div>
      )}
    </li>
  );
}
