import { useEffect, useState, type FormEvent, type ReactNode } from "react";
import { Link, useParams } from "react-router-dom";

import AiAnalysisCard from "../../components/complaints/AiAnalysisCard";
import AssignmentCard from "../../components/complaints/AssignmentCard";
import AttachmentImage from "../../components/complaints/AttachmentImage";
import FeedbackCard from "../../components/complaints/FeedbackCard";
import { ImageAnalysisToggle } from "../../components/complaints/ImageAnalysisResult";
import PriorityOverride from "../../components/complaints/PriorityOverride";
import SpeakButton from "../../components/voice/SpeakButton";
import { getAttachmentAnalysis } from "../../services/aiService";
import { PriorityBadge, StatusBadge } from "../../components/complaints/StatusBadge";
import Alert from "../../components/ui/Alert";
import Button from "../../components/ui/Button";
import Card from "../../components/ui/Card";
import Spinner from "../../components/ui/Spinner";
import { useAuth } from "../../hooks/useAuth";
import { getErrorMessage } from "../../services/api";
import { addComment, changeStatus, getComplaint } from "../../services/complaintService";
import type { ComplaintDetail, ComplaintStatus } from "../../types/complaint";
import { STATUS_LABELS, STATUS_ORDER, noteRequired, transitionLabel } from "../../utils/complaintLabels";
import { formatDateTime } from "../../utils/format";

export default function ComplaintDetailPage() {
  const { id } = useParams();
  const [complaint, setComplaint] = useState<ComplaintDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const complaintId = Number(id);
    if (!Number.isInteger(complaintId) || complaintId <= 0) {
      setError("Complaint not found.");
      setLoading(false);
      return;
    }
    setLoading(true);
    getComplaint(complaintId)
      .then(setComplaint)
      .catch((err) => setError(getErrorMessage(err)))
      .finally(() => setLoading(false));
  }, [id]);

  if (loading) return <Spinner label="Loading complaint" />;
  if (error || !complaint) {
    return (
      <div className="space-y-4">
        <Alert tone="error">{error ?? "Complaint not found."}</Alert>
        <Link to="/app/complaints" className="text-sm font-medium text-brand-600 hover:underline">
          ← Back to complaints
        </Link>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <Link to="/app/complaints" className="text-sm font-medium text-brand-600 hover:underline">
        ← Back to complaints
      </Link>

      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="font-mono text-sm text-slate-500">{complaint.reference_number}</p>
          <h1 className="mt-1 text-2xl font-bold tracking-tight break-words">{complaint.subject}</h1>
          <p className="mt-1 text-sm text-slate-500">
            Filed by {complaint.user.full_name} on {formatDateTime(complaint.created_at)}
          </p>
        </div>
        <div className="flex flex-col items-end gap-2">
          <StatusBadge status={complaint.status} />
          <SpeakButton
            text={`${complaint.subject}. Status: ${STATUS_LABELS[complaint.status]}. ${complaint.description}`}
          />
        </div>
      </div>

      <ProgressBar status={complaint.status} />

      <div className="grid gap-6 lg:grid-cols-3">
        <div className="space-y-6 lg:col-span-2">
          <Card title="Details">
            <p className="whitespace-pre-line text-sm text-slate-700">{complaint.description}</p>
            {complaint.attachments.length > 0 && (
              <div className="mt-5">
                <h3 className="text-sm font-medium text-slate-900">Photos</h3>
                <div className="mt-2 grid grid-cols-3 gap-3 sm:max-w-md">
                  {complaint.attachments.map((a) => (
                    <AttachmentImage key={a.id} complaintId={complaint.id} attachment={a} />
                  ))}
                </div>
                <ul className="mt-3 space-y-2" aria-label="Photo analysis">
                  {complaint.attachments.map((a) => (
                    <li key={a.id}>
                      <ImageAnalysisToggle
                        name={a.original_filename}
                        buttonLabel="Photo analysis"
                        load={() => getAttachmentAnalysis(complaint.id, a.id)}
                      />
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </Card>

          <ActionsPanel complaint={complaint} onUpdated={setComplaint} />
          <FeedbackCard complaint={complaint} />
          <CommentsPanel complaint={complaint} onUpdated={setComplaint} />
        </div>

        <div className="space-y-6">
          <AssignmentCard complaint={complaint} onUpdated={setComplaint} />
          <Card title="Summary">
            <dl className="space-y-3 text-sm">
              <Row label="Category">{complaint.category.name}</Row>
              <Row label="Department">{complaint.department?.name ?? "Not routed yet"}</Row>
              {complaint.assigned_to && !complaint.can_manage && <Row label="Handled by">{complaint.assigned_to.full_name}</Row>}
              <Row label={priorityLabel(complaint)}>
                <PriorityBadge priority={complaint.priority} />
              </Row>
              <Row label="Location">{complaint.location_text}</Row>
              {complaint.latitude != null && complaint.longitude != null && (
                <Row label="Coordinates">
                  <a
                    href={`https://www.openstreetmap.org/?mlat=${complaint.latitude}&mlon=${complaint.longitude}#map=18/${complaint.latitude}/${complaint.longitude}`}
                    target="_blank"
                    rel="noreferrer"
                    className="text-brand-600 hover:underline"
                  >
                    {complaint.latitude}, {complaint.longitude} ↗
                  </a>
                </Row>
              )}
              {complaint.incident_at && <Row label="Noticed on">{formatDateTime(complaint.incident_at)}</Row>}
              {complaint.resolved_at && <Row label="Resolved on">{formatDateTime(complaint.resolved_at)}</Row>}
              {complaint.closed_at && <Row label="Closed on">{formatDateTime(complaint.closed_at)}</Row>}
            </dl>
          </Card>

          {complaint.can_manage && (
            <>
              <PriorityOverride key={`${complaint.priority}-${complaint.priority_source}`} complaint={complaint} onUpdated={setComplaint} />
              <AiAnalysisCard complaintId={complaint.id} />
            </>
          )}

          <Card title="History">
            <ol className="relative space-y-4 border-l border-slate-200 pl-5">
              {complaint.history.map((entry) => (
                <li key={entry.id} className="relative">
                  <span className="absolute -left-[25px] top-1 h-2.5 w-2.5 rounded-full bg-brand-600 ring-4 ring-white" aria-hidden />
                  <p className="text-sm font-medium text-slate-900">
                    {entry.from_status === entry.to_status ? "Updated" : STATUS_LABELS[entry.to_status]}
                  </p>
                  <p className="text-xs text-slate-500">
                    {formatDateTime(entry.created_at)}
                    {entry.changed_by && ` · ${entry.changed_by.full_name}`}
                  </p>
                  {entry.note && <p className="mt-1 whitespace-pre-line text-sm text-slate-600">{entry.note}</p>}
                </li>
              ))}
            </ol>
          </Card>
        </div>
      </div>
    </div>
  );
}

/** Module 5: make clear whether the priority is an AI prediction or a staff decision. */
function priorityLabel(complaint: ComplaintDetail): string {
  if (complaint.priority_source === "ai") return "Priority (AI-predicted)";
  if (complaint.priority_source === "staff") return "Priority (set by staff)";
  return "Priority";
}

function Row({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div>
      <dt className="text-xs font-medium uppercase tracking-wide text-slate-500">{label}</dt>
      <dd className="mt-0.5 break-words text-slate-900">{children}</dd>
    </div>
  );
}

function ProgressBar({ status }: { status: ComplaintStatus }) {
  const current = STATUS_ORDER.indexOf(status);
  return (
    <ol className="grid grid-cols-5 gap-1" aria-label="Complaint progress">
      {STATUS_ORDER.map((step, index) => (
        <li key={step} aria-current={index === current ? "step" : undefined}>
          <div className={`h-1.5 rounded-full ${index <= current ? "bg-brand-600" : "bg-slate-200"}`} />
          <p className={`mt-1 text-[11px] sm:text-xs ${index <= current ? "font-medium text-slate-900" : "text-slate-400"}`}>{STATUS_LABELS[step]}</p>
        </li>
      ))}
    </ol>
  );
}

function ActionsPanel({ complaint, onUpdated }: { complaint: ComplaintDetail; onUpdated: (c: ComplaintDetail) => void }) {
  const { user } = useAuth();
  const [target, setTarget] = useState<ComplaintStatus | null>(null);
  const [note, setNote] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  if (complaint.allowed_transitions.length === 0) return null;
  const isOwner = complaint.user.id === user?.id;
  const needsNote = target ? noteRequired(complaint.status, target) : false;

  async function submit(event: FormEvent) {
    event.preventDefault();
    if (!target) return;
    if (needsNote && !note.trim()) {
      setError("Please add a note explaining this change.");
      return;
    }
    setSaving(true);
    setError(null);
    try {
      onUpdated(await changeStatus(complaint.id, target, note.trim()));
      setTarget(null);
      setNote("");
    } catch (err) {
      setError(getErrorMessage(err));
    } finally {
      setSaving(false);
    }
  }

  return (
    <Card
      title={isOwner && complaint.status === "resolved" ? "Was your problem resolved?" : "Update status"}
      description={isOwner && complaint.status === "resolved" ? "Confirm to close the complaint, or reopen it if the problem persists." : undefined}
    >
      <div className="flex flex-wrap gap-2">
        {complaint.allowed_transitions.map((status) => (
          <Button
            key={status}
            variant={target === status ? "primary" : "secondary"}
            onClick={() => {
              setTarget(status);
              setError(null);
            }}
            aria-pressed={target === status}
          >
            {transitionLabel(complaint.status, status, isOwner)}
          </Button>
        ))}
      </div>
      {target && (
        <form onSubmit={submit} className="mt-4 space-y-3">
          {error && <Alert tone="error">{error}</Alert>}
          <label htmlFor="status-note" className="block text-sm font-medium text-slate-700">
            Note {needsNote ? "(required)" : "(optional)"}
          </label>
          <textarea
            id="status-note"
            rows={3}
            maxLength={1000}
            value={note}
            onChange={(e) => setNote(e.target.value)}
            placeholder={target === "resolved" ? "What was done to resolve it?" : "Add context for this change"}
            className="block w-full rounded-lg border border-slate-300 px-3 py-2 text-sm shadow-sm focus:border-brand-500 focus:outline-none focus:ring-2 focus:ring-brand-100"
          />
          <div className="flex gap-2">
            <Button type="submit" disabled={saving}>
              {saving ? "Saving…" : `Confirm: ${STATUS_LABELS[target]}`}
            </Button>
            <Button variant="ghost" onClick={() => setTarget(null)}>
              Cancel
            </Button>
          </div>
        </form>
      )}
    </Card>
  );
}

function CommentsPanel({ complaint, onUpdated }: { complaint: ComplaintDetail; onUpdated: (c: ComplaintDetail) => void }) {
  // Admins and staff of the complaint's department may add internal notes.
  const isManager = complaint.can_manage;
  const [body, setBody] = useState("");
  const [internal, setInternal] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [posting, setPosting] = useState(false);
  const closedForUser = complaint.status === "closed" && !isManager;

  async function submit(event: FormEvent) {
    event.preventDefault();
    if (!body.trim()) return;
    setPosting(true);
    setError(null);
    try {
      onUpdated(await addComment(complaint.id, body.trim(), internal));
      setBody("");
      setInternal(false);
    } catch (err) {
      setError(getErrorMessage(err));
    } finally {
      setPosting(false);
    }
  }

  return (
    <Card title="Comments">
      {complaint.comments.length === 0 ? (
        <p className="text-sm text-slate-500">No comments yet.</p>
      ) : (
        <ul className="space-y-4">
          {complaint.comments.map((c) => (
            <li
              key={c.id}
              className={`rounded-lg border p-3 text-sm ${c.is_internal ? "border-amber-200 bg-amber-50" : "border-slate-200 bg-slate-50"}`}
            >
              <div className="flex flex-wrap items-center gap-2 text-xs text-slate-500">
                <span className="font-medium text-slate-900">{c.author?.full_name ?? "Deleted user"}</span>
                {(c.author?.role === "admin" || c.author?.role === "staff") && <span className="rounded bg-brand-100 px-1.5 py-0.5 text-brand-700">Staff</span>}
                {c.is_internal && <span className="rounded bg-amber-200 px-1.5 py-0.5 text-amber-900">Internal note</span>}
                <span>{formatDateTime(c.created_at)}</span>
              </div>
              <p className="mt-1 whitespace-pre-line text-slate-700">{c.body}</p>
            </li>
          ))}
        </ul>
      )}

      {closedForUser ? (
        <p className="mt-4 text-sm text-slate-500">This complaint is closed. Comments are no longer accepted.</p>
      ) : (
        <form onSubmit={submit} className="mt-4 space-y-3">
          {error && <Alert tone="error">{error}</Alert>}
          <label htmlFor="comment" className="sr-only">
            Add a comment
          </label>
          <textarea
            id="comment"
            rows={3}
            maxLength={2000}
            value={body}
            onChange={(e) => setBody(e.target.value)}
            placeholder="Write a comment…"
            className="block w-full rounded-lg border border-slate-300 px-3 py-2 text-sm shadow-sm focus:border-brand-500 focus:outline-none focus:ring-2 focus:ring-brand-100"
          />
          <div className="flex flex-wrap items-center justify-between gap-2">
            {isManager ? (
              <label className="flex items-center gap-2 text-sm text-slate-600">
                <input type="checkbox" checked={internal} onChange={(e) => setInternal(e.target.checked)} className="h-4 w-4 rounded border-slate-300" />
                Internal note (hidden from the complainant)
              </label>
            ) : (
              <span />
            )}
            <Button type="submit" disabled={posting || !body.trim()}>
              {posting ? "Posting…" : "Post comment"}
            </Button>
          </div>
        </form>
      )}
    </Card>
  );
}
