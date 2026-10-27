import { useId, type FormEvent, type ReactNode } from "react";

import type { ReportFilters } from "../../types/analytics";
import type { Category, ComplaintStatus, NamedRef } from "../../types/complaint";
import { STATUS_LABELS, STATUS_ORDER } from "../../utils/complaintLabels";

interface Props {
  value: ReportFilters;
  onChange: (filters: ReportFilters) => void;
  onSubmit?: () => void;
  categories: Category[];
  showCategory?: boolean;
  showDepartment?: boolean;
  showSearch?: boolean;
  error?: string | null;
  /** Action buttons rendered under the fields. */
  children?: ReactNode;
}

export const EMPTY_FILTERS: ReportFilters = {
  date_from: "", date_to: "", category_id: "", department_id: "", status: "", search: "",
};

/** Returns an error message when the date range is reversed. */
export function validateFilters(filters: ReportFilters): string | null {
  if (filters.date_from && filters.date_to && filters.date_from > filters.date_to) {
    return "The start date must be on or before the end date.";
  }
  return null;
}

/** Unique departments from the category -> department mapping, sorted by name. */
export function departmentsFrom(categories: Category[]): NamedRef[] {
  const byId = new Map<number, NamedRef>();
  categories.forEach((c) => byId.set(c.department.id, c.department));
  return [...byId.values()].sort((a, b) => a.name.localeCompare(b.name));
}

const fieldClass =
  "mt-1 block w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm shadow-sm focus:border-brand-500 focus:outline-none focus:ring-2 focus:ring-brand-100";
const labelClass = "block text-sm font-medium text-slate-700";

/** Date range (IST calendar dates), status and optional category / department / search filters. */
export default function ComplaintFilterBar({
  value, onChange, onSubmit, categories, showCategory = true, showDepartment = true, showSearch = false, error, children,
}: Props) {
  const id = useId();
  const set = (changes: Partial<ReportFilters>) => onChange({ ...value, ...changes });

  function submit(event: FormEvent) {
    event.preventDefault();
    onSubmit?.();
  }

  return (
    <form onSubmit={submit} aria-label="Filters" className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
        <div>
          <label htmlFor={`${id}-from`} className={labelClass}>From date</label>
          <input id={`${id}-from`} type="date" value={value.date_from ?? ""} aria-describedby={`${id}-tz`}
            onChange={(e) => set({ date_from: e.target.value })} className={fieldClass} />
        </div>
        <div>
          <label htmlFor={`${id}-to`} className={labelClass}>To date</label>
          <input id={`${id}-to`} type="date" value={value.date_to ?? ""} aria-describedby={`${id}-tz`}
            onChange={(e) => set({ date_to: e.target.value })} className={fieldClass} />
        </div>
        <div>
          <label htmlFor={`${id}-status`} className={labelClass}>Status</label>
          <select id={`${id}-status`} value={value.status ?? ""} className={fieldClass}
            onChange={(e) => set({ status: e.target.value as ComplaintStatus | "" })}>
            <option value="">All statuses</option>
            {STATUS_ORDER.map((s) => (
              <option key={s} value={s}>{STATUS_LABELS[s]}</option>
            ))}
          </select>
        </div>
        {showCategory && (
          <div>
            <label htmlFor={`${id}-category`} className={labelClass}>Category</label>
            <select id={`${id}-category`} value={value.category_id ?? ""} className={fieldClass}
              onChange={(e) => set({ category_id: e.target.value ? Number(e.target.value) : "" })}>
              <option value="">All categories</option>
              {categories.map((c) => (
                <option key={c.id} value={c.id}>{c.name}</option>
              ))}
            </select>
          </div>
        )}
        {showDepartment && (
          <div>
            <label htmlFor={`${id}-department`} className={labelClass}>Department</label>
            <select id={`${id}-department`} value={value.department_id ?? ""} className={fieldClass}
              onChange={(e) => set({ department_id: e.target.value ? Number(e.target.value) : "" })}>
              <option value="">All departments</option>
              {departmentsFrom(categories).map((d) => (
                <option key={d.id} value={d.id}>{d.name}</option>
              ))}
            </select>
          </div>
        )}
        {showSearch && (
          <div>
            <label htmlFor={`${id}-search`} className={labelClass}>Reference or subject</label>
            <input id={`${id}-search`} type="search" maxLength={100} value={value.search ?? ""} placeholder="CMP-… or keyword"
              onChange={(e) => set({ search: e.target.value })} className={fieldClass} />
          </div>
        )}
      </div>
      <p id={`${id}-tz`} className="mt-2 text-xs text-slate-500">
        Dates refer to when complaints were filed, include both ends, and use India Standard Time (IST).
      </p>
      {error && (
        <p role="alert" className="mt-2 text-sm text-red-600">
          {error}
        </p>
      )}
      {children && <div className="mt-3 flex flex-wrap gap-2">{children}</div>}
    </form>
  );
}
