import { Link } from "react-router-dom";

import Card, { type Accent } from "../components/ui/Card";
import { useAuth } from "../hooks/useAuth";
import { categoryStyle } from "../utils/categoryStyles";

const CATEGORIES = [
  ["drainage-sewerage", "Drainage"],
  ["garbage-sanitation", "Garbage"],
  ["roads-potholes", "Potholes"],
  ["street-lights", "Street lights"],
  ["water-supply", "Water supply"],
  ["electricity", "Electricity"],
  ["stray-animals", "Stray animals"],
  ["encroachment", "Encroachment"],
  ["public-health", "Mosquitoes"],
  ["pollution", "Pollution"],
  ["parks-trees", "Parks & trees"],
  ["other", "Anything else"],
] as const;

const FEATURES: { icon: string; title: string; text: string; accent: Accent }[] = [
  {
    icon: "🧠",
    title: "AI-assisted filing",
    text: "Describe the problem in your own words. AI suggests the category, department and priority, and you confirm before submitting.",
    accent: "violet",
  },
  {
    icon: "📍",
    title: "Find the right office",
    text: "A location-aware assistant points you to verified Hyderabad offices and official portals, with map directions.",
    accent: "sky",
  },
  {
    icon: "🔁",
    title: "Track every step",
    text: "Follow your complaint from Submitted to Closed with a reference number, status history and updates from staff.",
    accent: "teal",
  },
  {
    icon: "🎙️",
    title: "Speak or type",
    text: "Dictate your complaint in English or Telugu, attach photos, and review everything before it is sent.",
    accent: "amber",
  },
  {
    icon: "🧭",
    title: "Smart routing",
    text: "Complaints go to the responsible department automatically, and staff see similar complaints to avoid duplicate work.",
    accent: "rose",
  },
  {
    icon: "📊",
    title: "Transparent analytics",
    text: "Dashboards and downloadable reports are calculated from real complaint records only.",
    accent: "emerald",
  },
];

const STEPS = [
  { icon: "✍️", title: "Describe", text: "Tell us what is wrong, where, and add a photo if you can." },
  { icon: "🧠", title: "Confirm", text: "Review the AI's suggested category and priority, then submit." },
  { icon: "🏛️", title: "Routed", text: "The complaint reaches the responsible department with a reference number." },
  { icon: "✅", title: "Resolved", text: "Follow updates and confirm when the problem is fixed." },
];

export default function LandingPage() {
  const { status } = useAuth();
  const signedIn = status === "authenticated";

  return (
    <div className="relative min-h-screen overflow-hidden">
      {/* Decorative colour blobs */}
      <div aria-hidden className="pointer-events-none absolute -left-40 -top-40 h-[34rem] w-[34rem] rounded-full bg-brand-400/30 blur-3xl animate-float" />
      <div aria-hidden className="pointer-events-none absolute -right-32 top-20 h-[30rem] w-[30rem] rounded-full bg-fuchsia-400/25 blur-3xl animate-float [animation-delay:-3s]" />
      <div aria-hidden className="pointer-events-none absolute left-1/3 top-[40rem] h-96 w-96 rounded-full bg-sky-300/25 blur-3xl animate-float [animation-delay:-5s]" />

      <header className="relative mx-auto flex max-w-7xl items-center justify-between px-4 py-6 sm:px-8">
        <span className="flex items-center gap-3 text-xl font-extrabold tracking-tight text-slate-900 sm:text-2xl">
          <img src="/favicon.svg" alt="" className="h-10 w-10 sm:h-11 sm:w-11" />
          <span>
            Resolve<span className="text-gradient">AI</span>
          </span>
        </span>
        <nav className="flex items-center gap-2 sm:gap-3">
          {signedIn ? (
            <Link to="/app" className="rounded-xl bg-brand-gradient px-5 py-2.5 text-sm font-bold text-white shadow-[var(--shadow-soft)] hover:shadow-[var(--shadow-lift)] sm:text-base">
              Go to dashboard
            </Link>
          ) : (
            <>
              <Link to="/login" className="rounded-xl px-4 py-2.5 text-sm font-semibold text-slate-700 hover:bg-white/70 sm:text-base">
                Sign in
              </Link>
              <Link to="/register" className="rounded-xl bg-brand-gradient px-5 py-2.5 text-sm font-bold text-white shadow-[var(--shadow-soft)] transition hover:shadow-[var(--shadow-lift)] sm:text-base">
                Get started
              </Link>
            </>
          )}
        </nav>
      </header>

      <main className="relative mx-auto max-w-7xl px-4 pb-24 sm:px-8">
        {/* Hero: fills the first screen on desktop */}
        <section className="grid items-center gap-14 py-10 lg:min-h-[calc(100vh-7rem)] lg:grid-cols-[1.15fr_1fr] lg:py-0">
          <div className="animate-fade-up">
            <span className="inline-flex items-center gap-2 rounded-full border border-brand-200 bg-white/80 px-4 py-1.5 text-sm font-semibold text-brand-700 shadow-sm backdrop-blur">
              <span className="h-2.5 w-2.5 rounded-full bg-emerald-500 animate-pulse" />
              AI-powered civic complaints · Hyderabad
            </span>
            <h1 className="mt-6 text-5xl font-extrabold leading-[1.05] tracking-tight text-slate-900 sm:text-6xl lg:text-7xl xl:text-[5.25rem]">
              Report it once.
              <br />
              <span className="text-gradient-animated animate-gradient">We route it right.</span>
            </h1>
            <p className="mt-6 max-w-2xl text-lg leading-relaxed text-slate-600 sm:text-xl">
              File drainage, road, garbage, water or power complaints in minutes. ResolveAI understands your description, sends it to
              the responsible department and keeps you updated until it is resolved.
            </p>
            <div className="mt-9 flex flex-wrap gap-4">
              <Link
                to={signedIn ? "/app/complaints/new" : "/register"}
                className="group inline-flex items-center gap-2 rounded-2xl bg-brand-gradient px-8 py-4 text-base font-bold text-white shadow-[var(--shadow-lift)] transition hover:-translate-y-1 hover:brightness-110 sm:text-lg"
              >
                {signedIn ? "File a complaint" : "Create a free account"}
                <span aria-hidden className="transition group-hover:translate-x-1">→</span>
              </Link>
              <Link
                to={signedIn ? "/app/assistant" : "/login"}
                className="inline-flex items-center gap-2 rounded-2xl border border-slate-200 bg-white/85 px-8 py-4 text-base font-bold text-slate-700 shadow-sm backdrop-blur transition hover:-translate-y-1 hover:border-brand-300 hover:text-brand-700 sm:text-lg"
              >
                {signedIn ? "🤖 Ask the assistant" : "Sign in"}
              </Link>
            </div>
            <div className="mt-8 inline-flex items-center gap-2 rounded-xl border border-rose-200 bg-rose-50/80 px-4 py-2 text-sm text-rose-800">
              <span aria-hidden>🚨</span>
              Emergency? Fire, medical, gas leak or live wires: call <strong className="text-rose-600">112</strong> immediately.
            </div>
          </div>

          {/* Illustrative product preview (example content, not live data) */}
          <div className="relative mx-auto w-full max-w-xl animate-fade-up [animation-delay:120ms]" aria-label="Example of how a complaint is analysed">
            <div className="absolute -inset-6 rounded-[2.5rem] bg-brand-gradient opacity-25 blur-3xl" aria-hidden />

            <div className="relative space-y-4 rounded-[2rem] border border-white/70 glass p-6 shadow-[var(--shadow-lift)] sm:p-7">
              <div className="flex items-center justify-between">
                <p className="text-xs font-semibold uppercase tracking-wider text-slate-400">Example</p>
                <span className="flex gap-1.5" aria-hidden>
                  <span className="h-2.5 w-2.5 rounded-full bg-rose-400" />
                  <span className="h-2.5 w-2.5 rounded-full bg-amber-400" />
                  <span className="h-2.5 w-2.5 rounded-full bg-emerald-400" />
                </span>
              </div>
              <div className="rounded-2xl bg-white p-5 shadow-sm">
                <p className="text-base font-semibold text-slate-900 sm:text-lg">"Drain overflowing near the bus stop for 4 days"</p>
                <p className="mt-1 text-sm text-slate-500">📍 Ameerpet, Hyderabad · 📷 1 photo</p>
              </div>
              <div className="flex items-center gap-4 rounded-2xl bg-white p-5 shadow-sm">
                <span className="flex h-12 w-12 items-center justify-center rounded-2xl bg-sky-100 text-2xl">🚰</span>
                <div className="min-w-0 flex-1">
                  <p className="text-sm text-slate-500">AI suggestion</p>
                  <p className="text-base font-bold text-slate-900 sm:text-lg">Drainage &amp; Sewerage</p>
                  <div className="mt-2 h-2 overflow-hidden rounded-full bg-slate-100" aria-hidden>
                    <div className="h-full w-[82%] rounded-full bg-brand-gradient" />
                  </div>
                </div>
                <span className="rounded-full bg-violet-100 px-3 py-1 text-sm font-semibold text-violet-700">You confirm</span>
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div className="rounded-2xl bg-white p-4 shadow-sm">
                  <p className="text-sm text-slate-500">Priority</p>
                  <p className="text-lg font-bold text-orange-600">▲ High</p>
                </div>
                <div className="rounded-2xl bg-white p-4 shadow-sm">
                  <p className="text-sm text-slate-500">Reference</p>
                  <p className="font-mono text-base font-bold text-slate-900">CMP-2026-…</p>
                </div>
              </div>
              <div className="flex gap-2" aria-hidden>
                {["bg-violet-500", "bg-sky-500", "bg-amber-500", "bg-emerald-500", "bg-slate-200"].map((c) => (
                  <span key={c} className={`h-2 flex-1 rounded-full ${c}`} />
                ))}
              </div>
            </div>

            {/* Floating example badges */}
            <div aria-hidden className="absolute -left-6 top-24 hidden items-center gap-2 rounded-2xl bg-white px-4 py-3 text-sm font-semibold text-slate-700 shadow-[var(--shadow-lift)] animate-bob sm:flex">
              <span className="flex h-8 w-8 items-center justify-center rounded-xl bg-emerald-100">🗺️</span>
              Official office found
            </div>
            <div aria-hidden className="absolute -right-5 bottom-28 hidden items-center gap-2 rounded-2xl bg-white px-4 py-3 text-sm font-semibold text-slate-700 shadow-[var(--shadow-lift)] animate-bob [animation-delay:-2s] sm:flex">
              <span className="flex h-8 w-8 items-center justify-center rounded-xl bg-amber-100">🔔</span>
              Status: In progress
            </div>
            <div aria-hidden className="absolute -bottom-5 left-10 hidden items-center gap-2 rounded-2xl bg-white px-4 py-3 text-sm font-semibold text-slate-700 shadow-[var(--shadow-lift)] animate-bob [animation-delay:-1s] sm:flex">
              <span className="flex h-8 w-8 items-center justify-center rounded-xl bg-violet-100">🔁</span>
              Similar complaint linked
            </div>
          </div>
        </section>

        {/* Categories */}
        <section className="mt-16 lg:mt-8" aria-labelledby="categories-heading">
          <h2 id="categories-heading" className="text-center text-3xl font-extrabold tracking-tight text-slate-900 sm:text-4xl lg:text-5xl">
            What can you <span className="text-gradient">report</span>?
          </h2>
          <ul className="mx-auto mt-10 flex max-w-5xl flex-wrap justify-center gap-3 sm:gap-4">
            {CATEGORIES.map(([slug, label], index) => {
              const style = categoryStyle(slug);
              return (
                <li
                  key={slug}
                  className={`inline-flex items-center gap-2.5 rounded-full px-5 py-3 text-base font-semibold ring-1 transition hover:-translate-y-1 hover:shadow-lg animate-pop sm:text-lg ${style.chip}`}
                  style={{ animationDelay: `${index * 40}ms` }}
                >
                  <span aria-hidden className="text-xl">
                    {style.icon}
                  </span>
                  {label}
                </li>
              );
            })}
          </ul>
        </section>

        {/* How it works */}
        <section className="mt-28" aria-labelledby="steps-heading">
          <h2 id="steps-heading" className="text-center text-3xl font-extrabold tracking-tight text-slate-900 sm:text-4xl lg:text-5xl">
            How it works
          </h2>
          <ol className="mt-12 grid gap-6 sm:grid-cols-2 lg:grid-cols-4">
            {STEPS.map((step, index) => (
              <li
                key={step.title}
                className="group relative rounded-3xl border border-slate-200/80 bg-white/85 p-7 shadow-[var(--shadow-soft)] backdrop-blur transition hover:-translate-y-1 hover:shadow-[var(--shadow-lift)]"
              >
                <div className="flex items-center justify-between">
                  <span className="flex h-11 w-11 items-center justify-center rounded-full bg-brand-gradient text-lg font-bold text-white shadow">
                    {index + 1}
                  </span>
                  <span aria-hidden className="text-3xl transition group-hover:scale-125">
                    {step.icon}
                  </span>
                </div>
                <h3 className="mt-5 text-xl font-bold text-slate-900">{step.title}</h3>
                <p className="mt-2 text-base text-slate-600">{step.text}</p>
              </li>
            ))}
          </ol>
        </section>

        {/* Features */}
        <section className="mt-28" aria-labelledby="features-heading">
          <h2 id="features-heading" className="text-center text-3xl font-extrabold tracking-tight text-slate-900 sm:text-4xl lg:text-5xl">
            Built to get problems <span className="text-gradient">fixed</span>
          </h2>
          <div className="mt-12 grid gap-6 sm:grid-cols-2 lg:grid-cols-3">
            {FEATURES.map((feature) => (
              <Card key={feature.title} icon={feature.icon} accent={feature.accent} title={feature.title} description={feature.text} interactive className="p-7" />
            ))}
          </div>
        </section>

        {/* Call to action */}
        {!signedIn && (
          <section className="relative mt-28 overflow-hidden rounded-[2.5rem] bg-brand-gradient p-10 text-center text-white shadow-[var(--shadow-lift)] sm:p-16">
            <div aria-hidden className="absolute -right-16 -top-16 h-64 w-64 rounded-full bg-white/15 blur-2xl" />
            <div aria-hidden className="absolute -bottom-20 -left-10 h-64 w-64 rounded-full bg-sky-300/25 blur-2xl" />
            <h2 className="relative text-3xl font-extrabold sm:text-5xl">Spotted a problem in your area?</h2>
            <p className="relative mx-auto mt-4 max-w-2xl text-lg text-white/90 sm:text-xl">
              Create an account and file your first complaint in under two minutes.
            </p>
            <Link
              to="/register"
              className="relative mt-8 inline-block rounded-2xl bg-white px-8 py-4 text-lg font-bold text-brand-700 shadow-lg transition hover:-translate-y-1"
            >
              Get started free →
            </Link>
          </section>
        )}
      </main>

      <footer className="relative border-t border-slate-200/70 py-8 text-center text-sm text-slate-500">
        ResolveAI · Final-year project · AI-Powered Intelligent Complaint Management and Resolution System
      </footer>
    </div>
  );
}
