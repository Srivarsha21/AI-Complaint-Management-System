/** Mirrors the backend rules so users get instant feedback. The backend stays authoritative. */
export function validatePassword(password: string): string | null {
  if (password.length < 8) return "Password must be at least 8 characters.";
  if (password.length > 128) return "Password must be at most 128 characters.";
  if (!/[A-Za-z]/.test(password) || !/\d/.test(password)) {
    return "Password must contain at least one letter and one number.";
  }
  return null;
}

export function validateEmail(email: string): string | null {
  return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email.trim()) ? null : "Enter a valid email address.";
}

export function validateFullName(name: string): string | null {
  const cleaned = name.trim().replace(/\s+/g, " ");
  if (cleaned.length < 2) return "Full name must be at least 2 characters.";
  if (cleaned.length > 120) return "Full name must be at most 120 characters.";
  return null;
}
