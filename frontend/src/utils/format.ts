const dateTimeFormatter = new Intl.DateTimeFormat("en-IN", {
  dateStyle: "medium",
  timeStyle: "short",
  timeZone: "Asia/Kolkata",
});

export function formatDateTime(iso: string): string {
  return dateTimeFormatter.format(new Date(iso));
}

const isoDateInIst = new Intl.DateTimeFormat("en-CA", {
  year: "numeric",
  month: "2-digit",
  day: "2-digit",
  timeZone: "Asia/Kolkata",
});

/** Today's date in IST as YYYY-MM-DD. */
export function todayInIst(now: Date = new Date()): string {
  return isoDateInIst.format(now);
}

const shortDate = new Intl.DateTimeFormat("en-IN", { day: "numeric", month: "short", timeZone: "UTC" });

/** Formats a calendar date (YYYY-MM-DD, no time zone) such as "1 Oct". */
export function formatShortDate(isoDate: string): string {
  return shortDate.format(new Date(`${isoDate}T00:00:00Z`));
}

/** "18.5 hours" or, from two days up, "3.2 days". */
export function formatHours(hours: number | null): string {
  if (hours === null) return "—";
  if (hours < 48) return `${hours.toFixed(1)} hours`;
  return `${(hours / 24).toFixed(1)} days`;
}
