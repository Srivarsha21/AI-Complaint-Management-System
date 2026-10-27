import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";

import { useAuth } from "../../hooks/useAuth";
import { getErrorMessage } from "../../services/api";
import { getAuthConfig } from "../../services/authService";
import Alert from "../ui/Alert";

/** Minimal typing for Google Identity Services (https://accounts.google.com/gsi/client). */
interface GoogleAccountsId {
  initialize(options: { client_id: string; callback: (response: { credential?: string }) => void; ux_mode?: "popup" }): void;
  renderButton(element: HTMLElement, options: Record<string, string | number>): void;
}
declare global {
  interface Window {
    google?: { accounts: { id: GoogleAccountsId } };
  }
}

const GIS_SRC = "https://accounts.google.com/gsi/client";
let gisScript: Promise<void> | null = null;

function loadGoogleScript(): Promise<void> {
  gisScript ??= new Promise((resolve, reject) => {
    const script = document.createElement("script");
    script.src = GIS_SRC;
    script.async = true;
    script.defer = true;
    script.onload = () => resolve();
    script.onerror = () => {
      gisScript = null;
      reject(new Error("Could not load Google sign-in."));
    };
    document.head.appendChild(script);
  });
  return gisScript;
}

/**
 * "Continue with Google". Renders nothing when the server has no Google client ID,
 * so the email/password forms keep working on their own.
 */
export default function GoogleSignInButton({ text = "continue_with" }: { text?: "continue_with" | "signup_with" | "signin_with" }) {
  const { loginWithGoogle } = useAuth();
  const navigate = useNavigate();
  const container = useRef<HTMLDivElement>(null);
  const [clientId, setClientId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    // Promise.resolve keeps this safe even if the config call misbehaves; sign-in with email still works.
    Promise.resolve()
      .then(() => getAuthConfig())
      .then((config) => setClientId(config?.google_client_id ?? null))
      .catch(() => setClientId(null));
  }, []);

  useEffect(() => {
    if (!clientId || !container.current) return;
    let cancelled = false;
    loadGoogleScript()
      .then(() => {
        if (cancelled || !container.current || !window.google) return;
        window.google.accounts.id.initialize({
          client_id: clientId,
          ux_mode: "popup",
          callback: async ({ credential }) => {
            if (!credential) {
              setError("Google sign-in was cancelled.");
              return;
            }
            setBusy(true);
            setError(null);
            try {
              await loginWithGoogle(credential);
              navigate("/app", { replace: true });
            } catch (err) {
              setError(getErrorMessage(err));
            } finally {
              setBusy(false);
            }
          },
        });
        window.google.accounts.id.renderButton(container.current, {
          type: "standard",
          theme: "outline",
          size: "large",
          shape: "pill",
          text,
          logo_alignment: "left",
          width: Math.min(container.current.offsetWidth || 360, 400),
        });
      })
      .catch((err: Error) => !cancelled && setError(err.message));
    return () => {
      cancelled = true;
    };
  }, [clientId, loginWithGoogle, navigate, text]);

  if (!clientId) return null;

  return (
    <div className="space-y-3">
      <div className="flex items-center gap-3 text-xs font-medium uppercase tracking-wide text-slate-400">
        <span className="h-px flex-1 bg-slate-200" />
        or
        <span className="h-px flex-1 bg-slate-200" />
      </div>
      <div ref={container} className={`flex min-h-11 justify-center ${busy ? "pointer-events-none opacity-60" : ""}`} aria-busy={busy} />
      {error && <Alert tone="error">{error}</Alert>}
    </div>
  );
}
