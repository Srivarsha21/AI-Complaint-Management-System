import { useEffect, useMemo, useState, type ChangeEvent, type FormEvent } from "react";
import { Link, useSearchParams } from "react-router-dom";

import AiSuggestionPanel from "../../components/complaints/AiSuggestionPanel";
import Alert from "../../components/ui/Alert";
import Button from "../../components/ui/Button";
import Card from "../../components/ui/Card";
import Spinner from "../../components/ui/Spinner";
import TextField from "../../components/ui/TextField";
import { ImageAnalysisToggle } from "../../components/complaints/ImageAnalysisResult";
import TranslationReview from "../../components/voice/TranslationReview";
import VoiceInputButton from "../../components/voice/VoiceInputButton";
import { analyseImage } from "../../services/aiService";
import { getErrorMessage } from "../../services/api";
import { createComplaint, listCategories } from "../../services/complaintService";
import type { Category, ComplaintDetail } from "../../types/complaint";
import { appendText } from "../../utils/language";

const MAX_FILES = 3;
const MAX_FILE_MB = 5;
const ACCEPTED_TYPES = ["image/jpeg", "image/png", "image/webp"];
const SUBJECT_MAX = 150;
const DESCRIPTION_MAX = 5000;

interface Coordinates {
  latitude: number;
  longitude: number;
  accuracy: number;
}

interface FieldErrors {
  subject?: string;
  description?: string;
  category?: string;
  location?: string;
  incidentAt?: string;
}

/** "YYYY-MM-DDTHH:mm" in the browser's local time, as used by datetime-local inputs. */
function toLocalInputValue(date: Date): string {
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}T${pad(date.getHours())}:${pad(date.getMinutes())}`;
}

export default function NewComplaintPage() {
  // `?category=<id>` (e.g. from the complaint assistant) preselects a category.
  const [searchParams] = useSearchParams();
  const requestedCategory = searchParams.get("category");
  const [categories, setCategories] = useState<Category[]>([]);
  const [categoriesError, setCategoriesError] = useState<string | null>(null);
  const [loadingCategories, setLoadingCategories] = useState(true);

  const [subject, setSubject] = useState("");
  const [description, setDescription] = useState("");
  const [categoryId, setCategoryId] = useState("");
  const [locationText, setLocationText] = useState("");
  const [coords, setCoords] = useState<Coordinates | null>(null);
  const [locating, setLocating] = useState(false);
  const [locationMessage, setLocationMessage] = useState<string | null>(null);
  const [incidentAt, setIncidentAt] = useState(() => toLocalInputValue(new Date()));
  const [files, setFiles] = useState<File[]>([]);
  const [fileError, setFileError] = useState<string | null>(null);

  const [errors, setErrors] = useState<FieldErrors>({});
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [created, setCreated] = useState<ComplaintDetail | null>(null);
  // Module 5: the AI's top category suggestion, to record whether the citizen kept it.
  const [aiSuggestedId, setAiSuggestedId] = useState<number | null>(null);

  useEffect(() => {
    listCategories()
      .then((list) => {
        setCategories(list);
        if (requestedCategory && list.some((c) => String(c.id) === requestedCategory)) {
          setCategoryId((current) => current || requestedCategory);
        }
      })
      .catch((err) => setCategoriesError(getErrorMessage(err)))
      .finally(() => setLoadingCategories(false));
  }, [requestedCategory]);

  const selectedCategory = categories.find((c) => String(c.id) === categoryId);

  const previews = useMemo(() => files.map((file) => ({ file, url: URL.createObjectURL(file) })), [files]);
  useEffect(() => () => previews.forEach((p) => URL.revokeObjectURL(p.url)), [previews]);

  function handleFiles(event: ChangeEvent<HTMLInputElement>) {
    setFileError(null);
    const picked = Array.from(event.target.files ?? []);
    event.target.value = ""; // allow re-selecting the same file
    const next = [...files];
    for (const file of picked) {
      if (!ACCEPTED_TYPES.includes(file.type)) {
        setFileError(`"${file.name}" is not a JPEG, PNG or WebP image.`);
        continue;
      }
      if (file.size > MAX_FILE_MB * 1024 * 1024) {
        setFileError(`"${file.name}" is larger than ${MAX_FILE_MB} MB.`);
        continue;
      }
      if (next.length >= MAX_FILES) {
        setFileError(`You can attach up to ${MAX_FILES} images.`);
        break;
      }
      next.push(file);
    }
    setFiles(next);
  }

  function requestLocation() {
    setLocationMessage(null);
    if (!("geolocation" in navigator)) {
      setLocationMessage("Your browser does not support location access. Please type the address instead.");
      return;
    }
    setLocating(true);
    // The browser shows its own permission prompt; nothing is read without consent.
    navigator.geolocation.getCurrentPosition(
      (position) => {
        setCoords({
          latitude: Number(position.coords.latitude.toFixed(6)),
          longitude: Number(position.coords.longitude.toFixed(6)),
          accuracy: Math.round(position.coords.accuracy),
        });
        setLocating(false);
      },
      (error) => {
        setLocating(false);
        setLocationMessage(
          error.code === error.PERMISSION_DENIED
            ? "Location permission was denied. You can still type the address below."
            : "Could not get your location. Please type the address instead.",
        );
      },
      { enableHighAccuracy: true, timeout: 15000, maximumAge: 60000 },
    );
  }

  function validate(): FieldErrors {
    const result: FieldErrors = {};
    if (subject.trim().length < 5) result.subject = "Subject must be at least 5 characters.";
    if (description.trim().length < 20) result.description = "Please describe the problem in at least 20 characters.";
    if (!categoryId) result.category = "Choose a category.";
    if (locationText.trim().length < 3) result.location = "Enter the address or a nearby landmark.";
    if (incidentAt && new Date(incidentAt).getTime() > Date.now() + 5 * 60 * 1000) {
      result.incidentAt = "The incident date and time cannot be in the future.";
    }
    return result;
  }

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    setSubmitError(null);
    const found = validate();
    setErrors(found);
    if (Object.keys(found).length > 0) return;

    setSubmitting(true);
    try {
      const complaint = await createComplaint({
        subject: subject.trim(),
        description: description.trim(),
        category_id: Number(categoryId),
        location_text: locationText.trim(),
        latitude: coords?.latitude ?? null,
        longitude: coords?.longitude ?? null,
        incident_at: incidentAt ? new Date(incidentAt).toISOString() : null,
        attachments: files,
        ai_category_accepted: aiSuggestedId == null ? null : aiSuggestedId === Number(categoryId),
      });
      setCreated(complaint);
      window.scrollTo({ top: 0 });
    } catch (err) {
      setSubmitError(getErrorMessage(err));
    } finally {
      setSubmitting(false);
    }
  }

  function resetForm() {
    setSubject("");
    setDescription("");
    setCategoryId("");
    setLocationText("");
    setCoords(null);
    setIncidentAt(toLocalInputValue(new Date()));
    setFiles([]);
    setErrors({});
    setCreated(null);
    setAiSuggestedId(null);
  }

  if (created) {
    return <SubmissionSuccess complaint={created} onAnother={resetForm} />;
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">File a complaint</h1>
        <p className="mt-1 text-sm text-slate-500">
          Describe the problem clearly. You will receive a reference number to track it.
        </p>
      </div>

      <Alert tone="info">
        For emergencies such as fire, medical emergencies, gas leaks or live electric wires, call <strong>112</strong>{" "}
        immediately. This portal is not monitored for emergencies.
      </Alert>

      <form onSubmit={handleSubmit} noValidate className="space-y-6">
        {submitError && <Alert tone="error">{submitError}</Alert>}

        <Card title="What is the problem?">
          <div className="space-y-4">
            <div>
              <TextField
                label="Subject"
                value={subject}
                maxLength={SUBJECT_MAX}
                onChange={(e) => setSubject(e.target.value)}
                error={errors.subject}
                placeholder="e.g. Drain overflowing near the bus stop"
              />
              <p className="mt-1 text-right text-xs text-slate-400">
                {subject.length}/{SUBJECT_MAX}
              </p>
            </div>

            <div>
              <label htmlFor="description" className="block text-sm font-medium text-slate-700">
                Description
              </label>
              <textarea
                id="description"
                rows={6}
                maxLength={DESCRIPTION_MAX}
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                aria-invalid={Boolean(errors.description)}
                aria-describedby={errors.description ? "description-error" : undefined}
                placeholder="What is happening, since when, and how it affects people nearby."
                className={`mt-1 block w-full rounded-lg border bg-white px-3 py-2 text-sm shadow-sm focus:outline-none focus:ring-2 ${
                  errors.description ? "border-red-400 focus:ring-red-200" : "border-slate-300 focus:border-brand-500 focus:ring-brand-100"
                }`}
              />
              <div className="mt-1 flex justify-between text-xs">
                <span id="description-error" className="text-red-600">
                  {errors.description}
                </span>
                <span className="text-slate-400">
                  {description.length}/{DESCRIPTION_MAX}
                </span>
              </div>
              <div className="mt-2 space-y-2">
                <VoiceInputButton onTranscript={(text) => setDescription((d) => appendText(d, text, DESCRIPTION_MAX))} />
                <TranslationReview
                  text={description}
                  onAppend={(block) => setDescription((d) => appendText(d, block, DESCRIPTION_MAX, "\n\n"))}
                />
              </div>
            </div>

            <div>
              <label htmlFor="category" className="block text-sm font-medium text-slate-700">
                Category
              </label>
              {loadingCategories ? (
                <div className="mt-2">
                  <Spinner label="Loading categories" />
                </div>
              ) : categoriesError ? (
                <div className="mt-2">
                  <Alert tone="error">{categoriesError}</Alert>
                </div>
              ) : (
                <select
                  id="category"
                  value={categoryId}
                  onChange={(e) => setCategoryId(e.target.value)}
                  aria-invalid={Boolean(errors.category)}
                  className={`mt-1 block w-full rounded-lg border bg-white px-3 py-2 text-sm shadow-sm ${
                    errors.category ? "border-red-400" : "border-slate-300"
                  }`}
                >
                  <option value="">Select a category…</option>
                  {categories.map((category) => (
                    <option key={category.id} value={category.id}>
                      {category.name}
                    </option>
                  ))}
                </select>
              )}
              {errors.category && <p className="mt-1 text-xs text-red-600">{errors.category}</p>}
              {selectedCategory && (
                <p className="mt-2 text-xs text-slate-500">
                  {selectedCategory.description} Routed to: <strong>{selectedCategory.department.name}</strong>.
                </p>
              )}
            </div>
          </div>
        </Card>

        <AiSuggestionPanel
          subject={subject}
          description={description}
          latitude={coords?.latitude}
          longitude={coords?.longitude}
          categoryId={categoryId ? Number(categoryId) : null}
          onUseCategory={(id) => setCategoryId(String(id))}
          onSuggestion={setAiSuggestedId}
        />

        <Card title="Where and when?">
          <div className="space-y-4">
            <TextField
              label="Address or nearest landmark"
              value={locationText}
              maxLength={255}
              onChange={(e) => setLocationText(e.target.value)}
              error={errors.location}
              placeholder="e.g. Ameerpet Main Road, near Metro Station Pillar 1012, Hyderabad"
            />

            <div className="rounded-lg border border-slate-200 bg-slate-50 p-3">
              {coords ? (
                <div className="flex flex-wrap items-center justify-between gap-2 text-sm">
                  <span>
                    📍 {coords.latitude}, {coords.longitude}{" "}
                    <span className="text-slate-500">(accurate to about {coords.accuracy} m)</span>
                  </span>
                  <Button variant="ghost" onClick={() => setCoords(null)}>
                    Remove
                  </Button>
                </div>
              ) : (
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <p className="text-sm text-slate-600">Optionally attach your current GPS position to help locate the problem.</p>
                  <Button variant="secondary" onClick={requestLocation} disabled={locating}>
                    {locating ? "Locating…" : "Use my current location"}
                  </Button>
                </div>
              )}
              {locationMessage && <p className="mt-2 text-xs text-amber-700">{locationMessage}</p>}
            </div>

            <TextField
              label="When did you notice it?"
              type="datetime-local"
              value={incidentAt}
              max={toLocalInputValue(new Date())}
              onChange={(e) => setIncidentAt(e.target.value)}
              error={errors.incidentAt}
            />
          </div>
        </Card>

        <Card title="Photos (optional)" description={`Up to ${MAX_FILES} images, JPEG, PNG or WebP, ${MAX_FILE_MB} MB each.`}>
          <div className="space-y-3">
            {previews.length > 0 && (
              <ul className="grid grid-cols-3 gap-3 sm:max-w-md">
                {previews.map(({ file, url }, index) => (
                  <li key={url} className="relative">
                    <img src={url} alt={file.name} className="aspect-square w-full rounded-lg border border-slate-200 object-cover" />
                    <button
                      type="button"
                      onClick={() => setFiles((list) => list.filter((_, i) => i !== index))}
                      className="absolute right-1 top-1 rounded-full bg-white/90 px-2 py-0.5 text-xs font-medium text-slate-700 shadow hover:bg-white"
                      aria-label={`Remove ${file.name}`}
                    >
                      ✕
                    </button>
                  </li>
                ))}
              </ul>
            )}
            {previews.length > 0 && (
              <ul className="space-y-2 sm:max-w-xl" aria-label="Photo analysis">
                {previews.map(({ file, url }) => (
                  <li key={url}>
                    <ImageAnalysisToggle name={file.name} load={() => analyseImage(file)} />
                  </li>
                ))}
              </ul>
            )}
            {files.length < MAX_FILES && (
              <label className="inline-flex cursor-pointer items-center gap-2 rounded-lg border border-dashed border-slate-300 bg-white px-4 py-3 text-sm font-medium text-slate-700 hover:border-brand-500 hover:text-brand-700">
                <input type="file" accept={ACCEPTED_TYPES.join(",")} multiple className="sr-only" onChange={handleFiles} />
                + Add photos
              </label>
            )}
            {fileError && <p className="text-xs text-red-600">{fileError}</p>}
          </div>
        </Card>

        <div className="flex flex-wrap justify-end gap-3">
          <Link to="/app" className="rounded-lg px-4 py-2 text-sm font-medium text-slate-600 hover:bg-slate-100">
            Cancel
          </Link>
          <Button type="submit" disabled={submitting || loadingCategories || Boolean(categoriesError)}>
            {submitting ? "Submitting…" : "Submit complaint"}
          </Button>
        </div>
      </form>
    </div>
  );
}

function SubmissionSuccess({ complaint, onAnother }: { complaint: ComplaintDetail; onAnother: () => void }) {
  const [copied, setCopied] = useState(false);

  async function copyReference() {
    try {
      await navigator.clipboard.writeText(complaint.reference_number);
      setCopied(true);
    } catch {
      setCopied(false);
    }
  }

  return (
    <div className="mx-auto max-w-xl py-8 text-center">
      <div className="mx-auto flex h-14 w-14 items-center justify-center rounded-full bg-emerald-100 text-2xl text-emerald-700" aria-hidden>
        ✓
      </div>
      <h1 className="mt-4 text-2xl font-bold tracking-tight">Complaint submitted</h1>
      <p className="mt-2 text-slate-600">
        Routed to <strong>{complaint.department?.name ?? "the grievance cell"}</strong>. Keep this reference number to track it:
      </p>
      <div className="mt-4 inline-flex items-center gap-3 rounded-xl border border-slate-200 bg-white px-5 py-3 shadow-sm">
        <span className="font-mono text-lg font-semibold tracking-wide">{complaint.reference_number}</span>
        <Button variant="ghost" onClick={() => void copyReference()}>
          {copied ? "Copied" : "Copy"}
        </Button>
      </div>
      <div className="mt-8 flex flex-wrap justify-center gap-3">
        <Link to={`/app/complaints/${complaint.id}`} className="rounded-lg bg-brand-600 px-4 py-2 text-sm font-medium text-white hover:bg-brand-700">
          View complaint
        </Link>
        <Button variant="secondary" onClick={onAnother}>
          File another complaint
        </Button>
      </div>
    </div>
  );
}
