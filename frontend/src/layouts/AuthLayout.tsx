import { Link, Outlet } from "react-router-dom";

const HIGHLIGHTS = [
  { icon: "🧠", text: "AI suggests the right category and department" },
  { icon: "📍", text: "Find verified Hyderabad offices with directions" },
  { icon: "🔔", text: "Get updates until your complaint is resolved" },
];

/** Split layout for login, registration and password pages: form on the left, colour panel on the right. */
export default function AuthLayout() {
  return (
    <div className="grid min-h-screen lg:grid-cols-2">
      <div className="flex flex-col px-4 py-8 sm:px-8">
        <Link to="/" className="flex items-center gap-2 text-lg font-extrabold tracking-tight text-slate-900">
          <img src="/favicon.svg" alt="" className="h-9 w-9" />
          <span>
            Resolve<span className="text-gradient">AI</span>
          </span>
        </Link>
        <main className="mx-auto flex w-full max-w-md flex-1 flex-col justify-center py-10">
          <div className="rounded-3xl border border-slate-200/80 bg-white p-6 shadow-[var(--shadow-soft)] animate-fade-up sm:p-8">
            <Outlet />
          </div>
        </main>
      </div>

      <aside className="relative hidden overflow-hidden bg-brand-gradient lg:flex lg:flex-col lg:justify-center lg:px-14" aria-hidden>
        <div className="absolute -right-24 -top-24 h-96 w-96 rounded-full bg-white/15 blur-3xl animate-float" />
        <div className="absolute -bottom-32 -left-16 h-96 w-96 rounded-full bg-sky-300/30 blur-3xl animate-float [animation-delay:-4s]" />
        <div className="relative max-w-md text-white">
          <h2 className="text-4xl font-extrabold leading-tight">Your city, better — one complaint at a time.</h2>
          <p className="mt-4 text-white/85">File civic complaints, let AI route them, and follow every step to resolution.</p>
          <ul className="mt-10 space-y-4">
            {HIGHLIGHTS.map((h, index) => (
              <li
                key={h.text}
                className="flex items-center gap-3 rounded-2xl bg-white/15 px-4 py-3 backdrop-blur animate-fade-up"
                style={{ animationDelay: `${150 + index * 100}ms` }}
              >
                <span className="flex h-9 w-9 items-center justify-center rounded-xl bg-white/20 text-lg">{h.icon}</span>
                <span className="text-sm font-medium">{h.text}</span>
              </li>
            ))}
          </ul>
        </div>
      </aside>
    </div>
  );
}
