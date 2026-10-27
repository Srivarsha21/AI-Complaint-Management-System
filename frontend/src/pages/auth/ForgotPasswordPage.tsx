import { useState, type FormEvent } from "react";
import { Link } from "react-router-dom";

import Alert from "../../components/ui/Alert";
import Button from "../../components/ui/Button";
import TextField from "../../components/ui/TextField";
import { getErrorMessage } from "../../services/api";
import { requestPasswordReset } from "../../services/authService";
import { validateEmail } from "../../utils/validation";

export default function ForgotPasswordPage() {
  const [email, setEmail] = useState("");
  const [fieldError, setFieldError] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    setError(null);
    const invalid = validateEmail(email);
    setFieldError(invalid);
    if (invalid) return;

    setSubmitting(true);
    try {
      setMessage(await requestPasswordReset(email.trim()));
    } catch (err) {
      setError(getErrorMessage(err));
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <>
      <h1 className="text-2xl font-bold tracking-tight">Forgot your password?</h1>
      <p className="mt-1 text-sm text-slate-500">Enter your account email and we will send you a reset link.</p>

      {message ? (
        <div className="mt-6 space-y-4">
          <Alert tone="success">{message}</Alert>
          <p className="text-sm text-slate-500">The link expires in 30 minutes. Check your spam folder if it does not arrive.</p>
        </div>
      ) : (
        <form onSubmit={handleSubmit} noValidate className="mt-6 space-y-4">
          {error && <Alert tone="error">{error}</Alert>}
          <TextField label="Email" type="email" autoComplete="email" value={email} onChange={(e) => setEmail(e.target.value)} error={fieldError} />
          <Button type="submit" className="w-full" disabled={submitting}>
            {submitting ? "Sending…" : "Send reset link"}
          </Button>
        </form>
      )}

      <p className="mt-6 text-center text-sm">
        <Link to="/login" className="font-medium text-brand-600 hover:underline">
          Back to sign in
        </Link>
      </p>
    </>
  );
}
