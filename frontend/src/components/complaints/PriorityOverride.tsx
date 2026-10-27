import { useState, type FormEvent } from "react";

import { getErrorMessage } from "../../services/api";
import { overridePriority } from "../../services/aiService";
import type { ComplaintDetail, ComplaintPriority } from "../../types/complaint";
import { PRIORITY_LABELS } from "../../utils/complaintLabels";
import Button from "../ui/Button";
import Card from "../ui/Card";

const LEVELS: ComplaintPriority[] = ["low", "medium", "high", "critical"];

/** Staff-only control to set the priority; the change is recorded as "set by staff" and audited. */
export default function PriorityOverride({
  complaint,
  onUpdated,
}: {
  complaint: ComplaintDetail;
  onUpdated: (c: ComplaintDetail) => void;
}) {
  const [priority, setPriority] = useState<ComplaintPriority | "">(complaint.priority ?? "");
  const [note, setNote] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function submit(event: FormEvent) {
    event.preventDefault();
    if (!priority) return;
    setSaving(true);
    setError(null);
    try {
      onUpdated(await overridePriority(complaint.id, priority, note.trim()));
      setNote("");
    } catch (err) {
      setError(getErrorMessage(err));
    } finally {
      setSaving(false);
    }
  }

  const unchanged = priority === complaint.priority && complaint.priority_source === "staff";

  return (
    <Card title="Set priority" description="Overrides the AI prediction. The change is recorded in the history.">
      <form onSubmit={submit} className="space-y-3">
        {error && <p className="text-sm text-red-600">{error}</p>}
        <div>
          <label htmlFor="priority-override" className="block text-sm font-medium text-slate-700">
            Priority
          </label>
          <select
            id="priority-override"
            value={priority}
            onChange={(e) => setPriority(e.target.value as ComplaintPriority)}
            className="mt-1 block w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm shadow-sm"
          >
            <option value="" disabled>
              Choose…
            </option>
            {LEVELS.map((level) => (
              <option key={level} value={level}>
                {PRIORITY_LABELS[level]}
              </option>
            ))}
          </select>
        </div>
        <div>
          <label htmlFor="priority-note" className="block text-sm font-medium text-slate-700">
            Note (optional)
          </label>
          <input
            id="priority-note"
            maxLength={500}
            value={note}
            onChange={(e) => setNote(e.target.value)}
            className="mt-1 block w-full rounded-lg border border-slate-300 px-3 py-2 text-sm shadow-sm"
          />
        </div>
        <Button type="submit" disabled={saving || !priority || unchanged}>
          {saving ? "Saving…" : "Save priority"}
        </Button>
      </form>
    </Card>
  );
}
