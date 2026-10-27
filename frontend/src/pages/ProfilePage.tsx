import { useState, type FormEvent } from "react";

import Alert from "../components/ui/Alert";
import Button from "../components/ui/Button";
import Card from "../components/ui/Card";
import TextField from "../components/ui/TextField";
import { useAuth } from "../hooks/useAuth";
import { getErrorMessage } from "../services/api";
import { changePassword, updateProfile } from "../services/authService";
import { validateFullName, validatePassword } from "../utils/validation";

export default function ProfilePage() {
  const { user } = useAuth();
  if (!user) return null;

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">Profile</h1>
        <p className="mt-1 text-sm text-slate-500">Manage your account details and password.</p>
      </div>
      <div className="grid gap-6 lg:grid-cols-2">
        <ProfileForm />
        <PasswordForm />
      </div>
    </div>
  );
}

function ProfileForm() {
  const { user, setUser } = useAuth();
  const [fullName, setFullName] = useState(user?.full_name ?? "");
  const [fieldError, setFieldError] = useState<string | null>(null);
  const [result, setResult] = useState<{ tone: "success" | "error"; text: string } | null>(null);
  const [saving, setSaving] = useState(false);

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    setResult(null);
    const invalid = validateFullName(fullName);
    setFieldError(invalid);
    if (invalid) return;
    setSaving(true);
    try {
      const updated = await updateProfile(fullName.trim());
      setUser(updated);
      setFullName(updated.full_name);
      setResult({ tone: "success", text: "Profile updated." });
    } catch (err) {
      setResult({ tone: "error", text: getErrorMessage(err) });
    } finally {
      setSaving(false);
    }
  }

  return (
    <Card title="Account details">
      <form onSubmit={handleSubmit} noValidate className="space-y-4">
        {result && <Alert tone={result.tone}>{result.text}</Alert>}
        <TextField label="Full name" autoComplete="name" value={fullName} onChange={(e) => setFullName(e.target.value)} error={fieldError} />
        <TextField label="Email" value={user?.email ?? ""} disabled hint="Email cannot be changed." />
        <TextField
          label="Role"
          value={user?.role === "admin" ? "Administrator" : user?.role === "staff" ? `Staff · ${user.department?.name ?? "No department"}` : "User"}
          disabled
        />
        <Button type="submit" disabled={saving}>
          {saving ? "Saving…" : "Save changes"}
        </Button>
      </form>
    </Card>
  );
}

function PasswordForm() {
  const [current, setCurrent] = useState("");
  const [next, setNext] = useState("");
  const [confirm, setConfirm] = useState("");
  const [fieldErrors, setFieldErrors] = useState<{ next?: string | null; confirm?: string | null }>({});
  const [result, setResult] = useState<{ tone: "success" | "error"; text: string } | null>(null);
  const [saving, setSaving] = useState(false);

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    setResult(null);
    const errors = {
      next: validatePassword(next),
      confirm: next === confirm ? null : "Passwords do not match.",
    };
    setFieldErrors(errors);
    if (errors.next || errors.confirm) return;
    if (!current) {
      setResult({ tone: "error", text: "Enter your current password." });
      return;
    }
    setSaving(true);
    try {
      await changePassword(current, next);
      setCurrent("");
      setNext("");
      setConfirm("");
      setResult({ tone: "success", text: "Password changed. Other devices have been signed out." });
    } catch (err) {
      setResult({ tone: "error", text: getErrorMessage(err) });
    } finally {
      setSaving(false);
    }
  }

  return (
    <Card title="Change password">
      <form onSubmit={handleSubmit} noValidate className="space-y-4">
        {result && <Alert tone={result.tone}>{result.text}</Alert>}
        <TextField label="Current password" type="password" autoComplete="current-password" value={current} onChange={(e) => setCurrent(e.target.value)} />
        <TextField
          label="New password"
          type="password"
          autoComplete="new-password"
          value={next}
          onChange={(e) => setNext(e.target.value)}
          error={fieldErrors.next}
          hint="At least 8 characters, with a letter and a number."
        />
        <TextField label="Confirm new password" type="password" autoComplete="new-password" value={confirm} onChange={(e) => setConfirm(e.target.value)} error={fieldErrors.confirm} />
        <Button type="submit" disabled={saving}>
          {saving ? "Updating…" : "Update password"}
        </Button>
      </form>
    </Card>
  );
}
