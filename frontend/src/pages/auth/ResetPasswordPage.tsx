import { useEffect, useState, type FormEvent } from "react";
import { Link, useNavigate } from "react-router-dom";

import Alert from "../../components/ui/Alert";
import Button from "../../components/ui/Button";
import TextField from "../../components/ui/TextField";
import { getErrorMessage } from "../../services/api";
import { resetPassword } from "../../services/authService";
import { validatePassword } from "../../utils/validation";

/** Reads the one-time token from the URL fragment (#token=...), which browsers never send to servers. */
function readTokenFromHash(): string | null {
  const params = new URLSearchParams(window.location.hash.replace(/^#/, ""));
  return params.get("token");
}

export default function ResetPasswordPage() {
  const navigate = useNavigate();
  const [token] = useState(readTokenFromHash);
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [fieldErrors, setFieldErrors] = useState<{ password?: string | null; confirm?: string | null }>({});
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  // Remove the token from the address bar and history once read.
  useEffect(() => {
    if (window.location.hash) {
      window.history.replaceState(null, "", window.location.pathname);
    }
  }, []);

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    setError(null);
    const errors = {
      password: validatePassword(password),
      confirm: password === confirm ? null : "Passwords do not match.",
    };
    setFieldErrors(errors);
    if (errors.password || errors.confirm || !token) return;

    setSubmitting(true);
    try {
      await resetPassword(token, password);
      navigate("/login", { replace: true, state: { notice: "Your password has been reset. Please sign in." } });
    } catch (err) {
      setError(getErrorMessage(err));
    } finally {
      setSubmitting(false);
    }
  }

  if (!token) {
    return (
      <>
        <h1 className="text-2xl font-bold tracking-tight">Invalid reset link</h1>
        <p className="mt-2 text-sm text-slate-500">This link is incomplete. Please request a new password reset link.</p>
        <Link to="/forgot-password" className="mt-6 inline-block text-sm font-medium text-brand-600 hover:underline">
          Request a new link
        </Link>
      </>
    );
  }

  return (
    <>
      <h1 className="text-2xl font-bold tracking-tight">Choose a new password</h1>
      <p className="mt-1 text-sm text-slate-500">After resetting, you will be signed out on all devices.</p>

      <form onSubmit={handleSubmit} noValidate className="mt-6 space-y-4">
        {error && (
          <Alert tone="error">
            {error}{" "}
            <Link to="/forgot-password" className="font-medium underline">
              Request a new link
            </Link>
          </Alert>
        )}
        <TextField
          label="New password"
          type="password"
          autoComplete="new-password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          error={fieldErrors.password}
          hint="At least 8 characters, with a letter and a number."
        />
        <TextField
          label="Confirm new password"
          type="password"
          autoComplete="new-password"
          value={confirm}
          onChange={(e) => setConfirm(e.target.value)}
          error={fieldErrors.confirm}
        />
        <Button type="submit" className="w-full" disabled={submitting}>
          {submitting ? "Saving…" : "Reset password"}
        </Button>
      </form>
    </>
  );
}
