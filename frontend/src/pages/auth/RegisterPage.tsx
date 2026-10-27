import { useState, type FormEvent } from "react";
import { Link, useNavigate } from "react-router-dom";

import GoogleSignInButton from "../../components/auth/GoogleSignInButton";
import Alert from "../../components/ui/Alert";
import Button from "../../components/ui/Button";
import TextField from "../../components/ui/TextField";
import { useAuth } from "../../hooks/useAuth";
import { getErrorMessage } from "../../services/api";
import { validateEmail, validateFullName, validatePassword } from "../../utils/validation";

interface FieldErrors {
  fullName?: string | null;
  email?: string | null;
  password?: string | null;
  confirm?: string | null;
}

export default function RegisterPage() {
  const { register } = useAuth();
  const navigate = useNavigate();

  const [fullName, setFullName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [fieldErrors, setFieldErrors] = useState<FieldErrors>({});
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    setError(null);
    const errors: FieldErrors = {
      fullName: validateFullName(fullName),
      email: validateEmail(email),
      password: validatePassword(password),
      confirm: password === confirm ? null : "Passwords do not match.",
    };
    setFieldErrors(errors);
    if (Object.values(errors).some(Boolean)) return;

    setSubmitting(true);
    try {
      await register(fullName.trim(), email.trim(), password);
      navigate("/app", { replace: true });
    } catch (err) {
      setError(getErrorMessage(err));
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <>
      <h1 className="text-2xl font-bold tracking-tight">Create your account</h1>
      <p className="mt-1 text-sm text-slate-500">File complaints and follow their progress in one place.</p>

      <form onSubmit={handleSubmit} noValidate className="mt-6 space-y-4">
        {error && <Alert tone="error">{error}</Alert>}
        <TextField label="Full name" autoComplete="name" value={fullName} onChange={(e) => setFullName(e.target.value)} error={fieldErrors.fullName} />
        <TextField label="Email" type="email" autoComplete="email" value={email} onChange={(e) => setEmail(e.target.value)} error={fieldErrors.email} />
        <TextField
          label="Password"
          type="password"
          autoComplete="new-password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          error={fieldErrors.password}
          hint="At least 8 characters, with a letter and a number."
        />
        <TextField
          label="Confirm password"
          type="password"
          autoComplete="new-password"
          value={confirm}
          onChange={(e) => setConfirm(e.target.value)}
          error={fieldErrors.confirm}
        />
        <Button type="submit" className="w-full" disabled={submitting}>
          {submitting ? "Creating account…" : "Create account"}
        </Button>
      </form>

      <div className="mt-5">
        <GoogleSignInButton text="signup_with" />
      </div>

      <p className="mt-6 text-center text-sm text-slate-500">
        Already have an account?{" "}
        <Link to="/login" className="font-medium text-brand-600 hover:underline">
          Sign in
        </Link>
      </p>
    </>
  );
}
