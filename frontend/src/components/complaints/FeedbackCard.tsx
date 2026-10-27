import { useEffect, useState, type FormEvent } from "react";

import { useAuth } from "../../hooks/useAuth";
import { getErrorMessage } from "../../services/api";
import { getFeedback, submitFeedback } from "../../services/feedbackService";
import type { ComplaintDetail } from "../../types/complaint";
import type { Feedback } from "../../types/feedback";
import Alert from "../ui/Alert";
import Button from "../ui/Button";
import Card from "../ui/Card";

const RATING_WORDS = ["", "Very poor", "Poor", "Okay", "Good", "Excellent"];

/** Shown to the complainant once a complaint is resolved or closed (one feedback per complaint). */
export default function FeedbackCard({ complaint }: { complaint: ComplaintDetail }) {
  const { user } = useAuth();
  const isOwner = user?.id === complaint.user.id;
  const eligible = isOwner && (complaint.status === "resolved" || complaint.status === "closed");
  const [existing, setExisting] = useState<Feedback | null | undefined>(undefined);
  const [rating, setRating] = useState(0);
  const [satisfied, setSatisfied] = useState<boolean | null>(null);
  const [aiHelpful, setAiHelpful] = useState<boolean | null>(null);
  const [comment, setComment] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (!eligible) return;
    getFeedback(complaint.id)
      .then(setExisting)
      .catch(() => setExisting(null));
  }, [complaint.id, eligible]);

  if (!eligible || existing === undefined) return null;

  if (existing) {
    return (
      <Card title="Your feedback" icon="💬" accent="emerald">
        <p className="text-2xl" aria-label={`${existing.rating} out of 5 stars`}>
          {"★".repeat(existing.rating)}
          <span className="text-slate-300">{"★".repeat(5 - existing.rating)}</span>
        </p>
        <p className="mt-1 text-sm text-slate-600">
          {existing.resolved_satisfactorily ? "You said the problem was resolved." : "You said the problem was not fully resolved."}
        </p>
        {existing.comment && <p className="mt-2 text-sm italic text-slate-600">“{existing.comment}”</p>}
        <p className="mt-3 text-xs text-slate-400">Thank you. Feedback helps the department improve.</p>
      </Card>
    );
  }

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    if (rating === 0 || satisfied === null) {
      setError("Please choose a rating and tell us whether the problem was resolved.");
      return;
    }
    setSaving(true);
    setError(null);
    try {
      setExisting(await submitFeedback(complaint.id, { rating, resolved_satisfactorily: satisfied, ai_helpful: aiHelpful, comment }));
    } catch (err) {
      setError(getErrorMessage(err));
    } finally {
      setSaving(false);
    }
  }

  const choice = (active: boolean) =>
    `rounded-xl border px-3 py-1.5 text-sm font-medium transition ${
      active ? "border-brand-500 bg-brand-50 text-brand-700" : "border-slate-200 bg-white text-slate-600 hover:border-brand-300"
    }`;

  return (
    <Card title="How did we do?" description="Rate how your complaint was handled. You can do this once." icon="⭐" accent="amber">
      <form onSubmit={handleSubmit} className="space-y-4">
        {error && <Alert tone="error">{error}</Alert>}
        <fieldset>
          <legend className="text-sm font-medium text-slate-700">Overall rating</legend>
          <div className="mt-1 flex items-center gap-1" role="radiogroup" aria-label="Rating">
            {[1, 2, 3, 4, 5].map((value) => (
              <button
                key={value}
                type="button"
                role="radio"
                aria-checked={rating === value}
                aria-label={`${value} star${value > 1 ? "s" : ""} – ${RATING_WORDS[value]}`}
                onClick={() => setRating(value)}
                className={`text-3xl leading-none transition hover:scale-110 ${value <= rating ? "text-amber-400" : "text-slate-300"}`}
              >
                ★
              </button>
            ))}
            {rating > 0 && <span className="ml-2 text-sm font-medium text-slate-600">{RATING_WORDS[rating]}</span>}
          </div>
        </fieldset>

        <fieldset>
          <legend className="text-sm font-medium text-slate-700">Was the problem actually resolved?</legend>
          <div className="mt-1 flex gap-2">
            <button type="button" aria-pressed={satisfied === true} className={choice(satisfied === true)} onClick={() => setSatisfied(true)}>
              Yes
            </button>
            <button type="button" aria-pressed={satisfied === false} className={choice(satisfied === false)} onClick={() => setSatisfied(false)}>
              No
            </button>
          </div>
        </fieldset>

        <fieldset>
          <legend className="text-sm font-medium text-slate-700">Were the AI suggestions helpful when you filed it? (optional)</legend>
          <div className="mt-1 flex gap-2">
            <button type="button" aria-pressed={aiHelpful === true} className={choice(aiHelpful === true)} onClick={() => setAiHelpful(aiHelpful === true ? null : true)}>
              Helpful
            </button>
            <button type="button" aria-pressed={aiHelpful === false} className={choice(aiHelpful === false)} onClick={() => setAiHelpful(aiHelpful === false ? null : false)}>
              Not helpful
            </button>
          </div>
        </fieldset>

        <div>
          <label htmlFor="feedback-comment" className="text-sm font-medium text-slate-700">
            Comment (optional)
          </label>
          <textarea
            id="feedback-comment"
            rows={3}
            maxLength={1000}
            value={comment}
            onChange={(e) => setComment(e.target.value)}
            className="mt-1 block w-full rounded-xl border border-slate-300 px-3 py-2 text-sm shadow-sm focus:border-brand-500 focus:outline-none focus:ring-4 focus:ring-brand-100"
          />
        </div>
        <Button type="submit" disabled={saving}>
          {saving ? "Sending…" : "Send feedback"}
        </Button>
      </form>
    </Card>
  );
}
