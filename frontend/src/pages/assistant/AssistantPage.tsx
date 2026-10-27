import { lazy, Suspense, useEffect, useRef, useState, type FormEvent } from "react";
import { Link } from "react-router-dom";

import OfficeCard from "../../components/assistant/OfficeCard";
import Alert from "../../components/ui/Alert";
import Button from "../../components/ui/Button";
import Card from "../../components/ui/Card";
import Spinner from "../../components/ui/Spinner";
import { getErrorMessage } from "../../services/api";
import { sendChatMessage } from "../../services/assistantService";
import type { ChatMessage, ChatResponse, LocationInput } from "../../types/assistant";

// Leaflet is only needed once there is something to show on the map.
const OfficeMap = lazy(() => import("../../components/assistant/OfficeMap"));

const MAX_LENGTH = 1000;
const STARTER_SUGGESTIONS = [
  "Drainage problem in my area",
  "Garbage not collected for days",
  "Street light not working",
  "No water supply since morning",
  "Power cut in my street",
  "Big pothole on the main road",
];
const WELCOME =
  "Hi! Tell me about the civic problem you want to report in Hyderabad. I'll suggest the official office, " +
  "helpline or portal for it, using only verified government sources.";

interface DisplayMessage extends ChatMessage {
  id: number;
}

function describeLocation(location: LocationInput | null): string | null {
  if (!location) return null;
  return "text" in location ? location.text : "your current location";
}

export default function AssistantPage() {
  const [messages, setMessages] = useState<DisplayMessage[]>([]);
  const [input, setInput] = useState("");
  const [sending, setSending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [latest, setLatest] = useState<ChatResponse | null>(null);

  const [location, setLocation] = useState<LocationInput | null>(null);
  const [locality, setLocality] = useState("");
  const [locating, setLocating] = useState(false);
  const [locationMessage, setLocationMessage] = useState<string | null>(null);

  const nextId = useRef(1);
  const logRef = useRef<HTMLDivElement>(null);
  const localityRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    const log = logRef.current;
    if (log && typeof log.scrollTo === "function") log.scrollTo({ top: log.scrollHeight, behavior: "smooth" });
  }, [messages, sending]);

  function history(list: DisplayMessage[]): ChatMessage[] {
    return list.map(({ role, content }) => ({ role, content }));
  }

  async function ask(conversation: DisplayMessage[], where: LocationInput | null) {
    // The API needs the conversation to end with a user message.
    let end = conversation.length;
    while (end > 0 && conversation[end - 1].role !== "user") end -= 1;
    if (end === 0) return;

    setSending(true);
    setError(null);
    try {
      const response = await sendChatMessage(history(conversation.slice(0, end)), where);
      setLatest(response);
      setMessages((list) => [...list, { id: nextId.current++, role: "assistant", content: response.reply }]);
    } catch (err) {
      setError(getErrorMessage(err));
    } finally {
      setSending(false);
    }
  }

  function send(text: string) {
    const content = text.trim();
    if (!content || sending) return;
    const updated: DisplayMessage[] = [...messages, { id: nextId.current++, role: "user", content }];
    setMessages(updated);
    setInput("");
    void ask(updated, location);
  }

  function handleSubmit(event: FormEvent) {
    event.preventDefault();
    send(input);
  }

  function applyLocation(where: LocationInput) {
    setLocation(where);
    // Refresh the guidance for the problem already described.
    if (messages.some((m) => m.role === "user")) void ask(messages, where);
  }

  function shareLocation() {
    setLocationMessage(null);
    if (!("geolocation" in navigator)) {
      setLocationMessage("Your browser cannot share location. Type your locality or PIN code instead.");
      localityRef.current?.focus();
      return;
    }
    setLocating(true);
    // The browser asks the user for permission; nothing is read without consent.
    navigator.geolocation.getCurrentPosition(
      (position) => {
        setLocating(false);
        applyLocation({
          latitude: Number(position.coords.latitude.toFixed(5)),
          longitude: Number(position.coords.longitude.toFixed(5)),
        });
      },
      (geoError) => {
        setLocating(false);
        setLocationMessage(
          geoError.code === geoError.PERMISSION_DENIED
            ? "Location permission was denied. Type your locality or PIN code instead."
            : "Could not get your location. Type your locality or PIN code instead.",
        );
        localityRef.current?.focus();
      },
      { enableHighAccuracy: false, timeout: 15000, maximumAge: 300000 },
    );
  }

  function handleLocality(event: FormEvent) {
    event.preventDefault();
    const text = locality.trim();
    if (text.length < 3) {
      setLocationMessage("Enter at least 3 characters, for example \"Ameerpet\" or \"500016\".");
      return;
    }
    setLocationMessage(null);
    applyLocation({ text });
  }

  function clearLocation() {
    setLocation(null);
    setLocality("");
    setLocationMessage(null);
  }

  const suggestions = latest?.suggestions.length ? latest.suggestions : messages.length === 0 ? STARTER_SUGGESTIONS : [];
  const devicePosition = location && "latitude" in location ? location : null;
  const mapPosition = latest?.location ?? devicePosition;
  const hasMappableOffice = latest?.offices.some((o) => o.latitude != null && o.longitude != null) ?? false;
  const locationLabel = describeLocation(location);

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">Complaint assistant</h1>
        <p className="mt-1 text-sm text-slate-500">
          Describe a problem and get the official office, helpline or portal to report it to. Information comes only
          from official government websites.
        </p>
      </div>

      <Alert tone="info">
        For emergencies such as fire, accidents, gas leaks or live electric wires, call <strong>112</strong> immediately.
      </Alert>

      <div className="grid gap-6 lg:grid-cols-5">
        {/* Conversation */}
        <section aria-labelledby="chat-heading" className="flex flex-col rounded-xl border border-slate-200 bg-white shadow-sm lg:col-span-2">
          <h2 id="chat-heading" className="sr-only">
            Conversation
          </h2>
          <div
            ref={logRef}
            role="log"
            aria-live="polite"
            aria-relevant="additions"
            aria-label="Conversation with the complaint assistant"
            className="h-[26rem] space-y-3 overflow-y-auto p-4"
          >
            <Bubble role="assistant" content={WELCOME} />
            {messages.map((message) => (
              <Bubble key={message.id} role={message.role} content={message.content} />
            ))}
            {sending && (
              <div className="pl-1">
                <Spinner label="Assistant is typing" />
              </div>
            )}
          </div>

          {error && (
            <div className="px-4 pb-2">
              <Alert tone="error">{error}</Alert>
            </div>
          )}

          {suggestions.length > 0 && (
            <div className="border-t border-slate-100 px-4 py-3">
              <p id="suggestions-label" className="mb-2 text-xs font-medium text-slate-500">
                Try one of these
              </p>
              <ul aria-labelledby="suggestions-label" className="flex flex-wrap gap-2">
                {suggestions.map((suggestion) => (
                  <li key={suggestion}>
                    <button
                      type="button"
                      onClick={() => send(suggestion)}
                      disabled={sending}
                      className="rounded-full border border-brand-100 bg-brand-50 px-3 py-1 text-xs font-medium text-brand-700 hover:bg-brand-100 disabled:opacity-60"
                    >
                      {suggestion}
                    </button>
                  </li>
                ))}
              </ul>
            </div>
          )}

          <form onSubmit={handleSubmit} className="flex gap-2 border-t border-slate-200 p-3">
            <label htmlFor="chat-input" className="sr-only">
              Describe your problem
            </label>
            <input
              id="chat-input"
              value={input}
              maxLength={MAX_LENGTH}
              onChange={(e) => setInput(e.target.value)}
              placeholder="e.g. Drain overflowing near the bus stop"
              autoComplete="off"
              className="min-w-0 flex-1 rounded-lg border border-slate-300 px-3 py-2 text-sm shadow-sm focus:border-brand-500 focus:outline-none focus:ring-2 focus:ring-brand-100"
            />
            <Button type="submit" disabled={sending || !input.trim()}>
              Send
            </Button>
          </form>

          {/* Location */}
          <div className="space-y-2 border-t border-slate-200 p-3">
            <div className="flex flex-wrap items-center gap-2">
              <Button variant="secondary" onClick={shareLocation} disabled={locating || sending}>
                {locating ? "Locating…" : "Share my location"}
              </Button>
              <span className="text-xs text-slate-500">Used only to find nearby offices; not saved.</span>
            </div>
            <form onSubmit={handleLocality} className="flex gap-2">
              <label htmlFor="locality-input" className="sr-only">
                Locality or PIN code
              </label>
              <input
                id="locality-input"
                ref={localityRef}
                value={locality}
                maxLength={200}
                onChange={(e) => setLocality(e.target.value)}
                placeholder="Or type locality / PIN code, e.g. Ameerpet or 500016"
                className="min-w-0 flex-1 rounded-lg border border-slate-300 px-3 py-2 text-sm shadow-sm focus:border-brand-500 focus:outline-none focus:ring-2 focus:ring-brand-100"
              />
              <Button type="submit" variant="secondary" disabled={sending}>
                Use
              </Button>
            </form>
            {locationLabel && (
              <p className="flex flex-wrap items-center gap-2 text-xs text-slate-600">
                Location: <strong>{locationLabel}</strong>
                <button type="button" onClick={clearLocation} className="underline hover:text-slate-900">
                  Clear
                </button>
              </p>
            )}
            {locationMessage && (
              <p role="status" className="text-xs text-amber-700">
                {locationMessage}
              </p>
            )}
          </div>
        </section>

        {/* Guidance */}
        <section aria-labelledby="guidance-heading" className="space-y-4 lg:col-span-3">
          <h2 id="guidance-heading" className="text-lg font-semibold">
            {latest?.category ? `Where to report: ${latest.category.name}` : "Where to report"}
          </h2>

          {!latest?.category ? (
            <p className="text-sm text-slate-500">Describe your problem to see verified offices and channels here.</p>
          ) : (
            <>
              {latest.file_complaint && (
                <div className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-brand-100 bg-brand-50 p-4">
                  <p className="text-sm text-brand-900">Want this tracked here? File it in this app and get a reference number.</p>
                  <Link
                    to={`/app/complaints/new?category=${latest.file_complaint.category_id}`}
                    className="rounded-lg bg-brand-600 px-4 py-2 text-sm font-medium text-white hover:bg-brand-700"
                  >
                    File a complaint in this category
                  </Link>
                </div>
              )}

              {latest.needs_location && (
                <Alert tone="info">Share your location or type your locality / PIN code to see the nearest offices.</Alert>
              )}

              {hasMappableOffice && (
                <Suspense fallback={<Spinner label="Loading map" />}>
                  <OfficeMap offices={latest.offices} userPosition={mapPosition} />
                </Suspense>
              )}

              {latest.offices.length > 0 && (
                <div className="space-y-3">
                  <h3 className="text-sm font-semibold uppercase tracking-wide text-slate-500">Offices</h3>
                  {latest.offices.map((office) => (
                    <OfficeCard key={office.id} office={office} />
                  ))}
                </div>
              )}

              {latest.channels.length > 0 && (
                <div className="space-y-3">
                  <h3 className="text-sm font-semibold uppercase tracking-wide text-slate-500">Helplines, portals and apps</h3>
                  {latest.channels.map((channel) => (
                    <OfficeCard key={channel.id} office={channel} />
                  ))}
                </div>
              )}

              {latest.steps.length > 0 && (
                <Card title="Before you complain">
                  <ol className="list-decimal space-y-1 pl-5 text-sm text-slate-700">
                    {latest.steps.map((step) => (
                      <li key={step}>{step}</li>
                    ))}
                  </ol>
                </Card>
              )}

              {latest.documents && latest.documents.length > 0 && (
                <Card title="Documents">
                  <ul className="list-disc space-y-1 pl-5 text-sm text-slate-700">
                    {latest.documents.map((doc) => (
                      <li key={doc}>{doc}</li>
                    ))}
                  </ul>
                </Card>
              )}
            </>
          )}

          {latest && <p className="text-xs text-slate-500">{latest.disclaimer}</p>}
        </section>
      </div>
    </div>
  );
}

function Bubble({ role, content }: ChatMessage) {
  const mine = role === "user";
  return (
    <div className={`flex ${mine ? "justify-end" : "justify-start"}`}>
      <div
        className={`max-w-[85%] whitespace-pre-line rounded-2xl px-3 py-2 text-sm ${
          mine ? "bg-brand-600 text-white" : "bg-slate-100 text-slate-800"
        }`}
      >
        <span className="sr-only">{mine ? "You said: " : "Assistant: "}</span>
        {content}
      </div>
    </div>
  );
}
