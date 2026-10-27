import { useCallback, useEffect, useId, useState, type FormEvent } from "react";

import Alert from "../../components/ui/Alert";
import Button from "../../components/ui/Button";
import Card from "../../components/ui/Card";
import Spinner from "../../components/ui/Spinner";
import StatusPill from "../../components/ui/StatusPill";
import TextField from "../../components/ui/TextField";
import { getErrorMessage } from "../../services/api";
import {
  createCategory,
  createDepartment,
  listAdminCategories,
  listDepartments,
  updateCategory,
  updateDepartment,
} from "../../services/departmentService";
import type { AdminCategory, Department } from "../../types/department";
import {
  slugify,
  validateCategoryForm,
  validateDepartmentForm,
  type CategoryForm,
  type DepartmentForm,
  type FieldErrors,
} from "../../utils/departmentValidation";

const EMPTY_DEPARTMENT: DepartmentForm = { name: "", description: "", contact_email: "" };
const EMPTY_CATEGORY: CategoryForm = { name: "", slug: "", description: "", department_id: "" };

const INPUT = "mt-1 block w-full rounded-lg border bg-white px-3 py-2 text-sm shadow-sm focus:outline-none focus:ring-2";
const inputTone = (error?: string) => (error ? "border-red-400 focus:ring-red-200" : "border-slate-300 focus:border-brand-500 focus:ring-brand-100");

/** "new" opens an empty form; a number edits that row; null hides the form. */
type Editing = "new" | number | null;

export default function DepartmentsPage() {
  const [departments, setDepartments] = useState<Department[]>([]);
  const [categories, setCategories] = useState<AdminCategory[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [depts, cats] = await Promise.all([listDepartments(), listAdminCategories()]);
      setDepartments(depts);
      setCategories(cats);
    } catch (err) {
      setError(getErrorMessage(err));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  function announce(message: string) {
    setError(null);
    setNotice(message);
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">Departments &amp; categories</h1>
        <p className="mt-1 text-sm text-slate-500">
          Each category routes new complaints to a department. Changing a mapping affects only complaints filed afterwards.
          Every change is recorded in the audit log.
        </p>
      </div>

      {notice && <Alert tone="success">{notice}</Alert>}
      {error && <Alert tone="error">{error}</Alert>}

      {loading ? (
        <Spinner label="Loading departments" />
      ) : (
        <>
          <DepartmentsSection
            departments={departments}
            onSaved={(saved, message) => {
              setDepartments((list) => upsert(list, saved).sort((a, b) => a.name.localeCompare(b.name)));
              // Category rows show department names, so refresh them after a rename.
              void listAdminCategories().then(setCategories).catch(() => undefined);
              announce(message);
            }}
            onError={setError}
          />
          <CategoriesSection
            categories={categories}
            departments={departments}
            onSaved={(saved, message) => {
              setCategories((list) => upsert(list, saved).sort((a, b) => a.name.localeCompare(b.name)));
              announce(message);
            }}
            onError={setError}
          />
        </>
      )}
    </div>
  );
}

function upsert<T extends { id: number }>(list: T[], item: T): T[] {
  return list.some((x) => x.id === item.id) ? list.map((x) => (x.id === item.id ? item : x)) : [...list, item];
}

// --- Departments -----------------------------------------------------------------

function DepartmentsSection({
  departments,
  onSaved,
  onError,
}: {
  departments: Department[];
  onSaved: (d: Department, message: string) => void;
  onError: (message: string) => void;
}) {
  const [editing, setEditing] = useState<Editing>(null);
  const [busyId, setBusyId] = useState<number | null>(null);
  const current = typeof editing === "number" ? departments.find((d) => d.id === editing) : undefined;

  async function toggle(dept: Department) {
    setBusyId(dept.id);
    try {
      const saved = await updateDepartment(dept.id, { is_active: !dept.is_active });
      onSaved(saved, `${saved.name} ${saved.is_active ? "activated" : "deactivated"}.`);
    } catch (err) {
      onError(getErrorMessage(err));
    } finally {
      setBusyId(null);
    }
  }

  return (
    <Card title="Departments" description="Internal routing units that receive and handle complaints.">
      {editing === null ? (
        <Button onClick={() => setEditing("new")}>New department</Button>
      ) : (
        <DepartmentEditor
          key={String(editing)}
          department={current}
          onCancel={() => setEditing(null)}
          onSaved={(saved) => {
            setEditing(null);
            onSaved(saved, current ? `${saved.name} updated.` : `${saved.name} created.`);
          }}
        />
      )}

      <div className="mt-4 overflow-x-auto rounded-lg border border-slate-200">
        <table className="min-w-full divide-y divide-slate-200 text-sm">
          <thead className="bg-slate-50 text-left text-xs font-semibold uppercase tracking-wide text-slate-500">
            <tr>
              <th scope="col" className="px-4 py-3">Name</th>
              <th scope="col" className="px-4 py-3">Contact</th>
              <th scope="col" className="px-4 py-3">Status</th>
              <th scope="col" className="px-4 py-3 text-right">Actions</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {departments.length === 0 ? (
              <tr>
                <td colSpan={4} className="px-4 py-6 text-center text-slate-500">No departments yet.</td>
              </tr>
            ) : (
              departments.map((d) => (
                <tr key={d.id}>
                  <td className="px-4 py-3">
                    <div className="font-medium text-slate-900">{d.name}</div>
                    {d.description && <div className="text-slate-500">{d.description}</div>}
                  </td>
                  <td className="px-4 py-3 text-slate-500">{d.contact_email ?? "—"}</td>
                  <td className="px-4 py-3">
                    {d.is_active ? <StatusPill tone="success">Active</StatusPill> : <StatusPill tone="neutral">Inactive</StatusPill>}
                  </td>
                  <td className="px-4 py-3">
                    <div className="flex justify-end gap-2">
                      <Button variant="ghost" onClick={() => setEditing(d.id)} aria-label={`Edit ${d.name}`}>
                        Edit
                      </Button>
                      <Button variant="secondary" disabled={busyId === d.id} onClick={() => void toggle(d)}>
                        {d.is_active ? "Deactivate" : "Activate"}
                      </Button>
                    </div>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </Card>
  );
}

function DepartmentEditor({
  department,
  onCancel,
  onSaved,
}: {
  department?: Department;
  onCancel: () => void;
  onSaved: (d: Department) => void;
}) {
  const [form, setForm] = useState<DepartmentForm>(
    department
      ? { name: department.name, description: department.description ?? "", contact_email: department.contact_email ?? "" }
      : EMPTY_DEPARTMENT,
  );
  const [errors, setErrors] = useState<FieldErrors<keyof DepartmentForm>>({});
  const [serverError, setServerError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const set = (field: keyof DepartmentForm) => (value: string) => setForm((f) => ({ ...f, [field]: value }));

  async function submit(event: FormEvent) {
    event.preventDefault();
    const found = validateDepartmentForm(form);
    setErrors(found);
    if (Object.keys(found).length > 0) return;
    const payload = {
      name: form.name.trim(),
      description: form.description.trim() || null,
      contact_email: form.contact_email.trim() || null,
    };
    setSaving(true);
    setServerError(null);
    try {
      onSaved(department ? await updateDepartment(department.id, payload) : await createDepartment(payload));
    } catch (err) {
      setServerError(getErrorMessage(err));
    } finally {
      setSaving(false);
    }
  }

  return (
    <form onSubmit={submit} noValidate className="space-y-3 rounded-lg border border-slate-200 bg-slate-50 p-4" aria-label="Department form">
      <h3 className="text-sm font-semibold text-slate-900">{department ? `Edit ${department.name}` : "New department"}</h3>
      {serverError && <Alert tone="error">{serverError}</Alert>}
      <div className="grid gap-3 sm:grid-cols-2">
        <TextField label="Department name" value={form.name} onChange={(e) => set("name")(e.target.value)} error={errors.name} maxLength={120} />
        <TextField
          label="Contact email (optional)"
          type="email"
          value={form.contact_email}
          onChange={(e) => set("contact_email")(e.target.value)}
          error={errors.contact_email}
        />
      </div>
      <TextArea label="Description (optional)" value={form.description} onChange={set("description")} error={errors.description} />
      <div className="flex gap-2">
        <Button type="submit" disabled={saving}>
          {saving ? "Saving…" : department ? "Save department" : "Create department"}
        </Button>
        <Button variant="ghost" onClick={onCancel}>
          Cancel
        </Button>
      </div>
    </form>
  );
}

// --- Categories --------------------------------------------------------------------

function CategoriesSection({
  categories,
  departments,
  onSaved,
  onError,
}: {
  categories: AdminCategory[];
  departments: Department[];
  onSaved: (c: AdminCategory, message: string) => void;
  onError: (message: string) => void;
}) {
  const [editing, setEditing] = useState<Editing>(null);
  const [busyId, setBusyId] = useState<number | null>(null);
  const current = typeof editing === "number" ? categories.find((c) => c.id === editing) : undefined;

  async function toggle(category: AdminCategory) {
    setBusyId(category.id);
    try {
      const saved = await updateCategory(category.id, { is_active: !category.is_active });
      onSaved(saved, `${saved.name} ${saved.is_active ? "activated" : "deactivated"}.`);
    } catch (err) {
      onError(getErrorMessage(err));
    } finally {
      setBusyId(null);
    }
  }

  return (
    <Card title="Categories" description="What citizens choose when filing a complaint, and where it is routed.">
      {editing === null ? (
        <Button onClick={() => setEditing("new")} disabled={departments.length === 0}>
          New category
        </Button>
      ) : (
        <CategoryEditor
          key={String(editing)}
          category={current}
          departments={departments}
          onCancel={() => setEditing(null)}
          onSaved={(saved) => {
            setEditing(null);
            onSaved(saved, current ? `${saved.name} updated.` : `${saved.name} created.`);
          }}
        />
      )}
      {departments.length === 0 && <p className="mt-2 text-sm text-slate-500">Create a department first.</p>}

      <div className="mt-4 overflow-x-auto rounded-lg border border-slate-200">
        <table className="min-w-full divide-y divide-slate-200 text-sm">
          <thead className="bg-slate-50 text-left text-xs font-semibold uppercase tracking-wide text-slate-500">
            <tr>
              <th scope="col" className="px-4 py-3">Category</th>
              <th scope="col" className="px-4 py-3">Routed to</th>
              <th scope="col" className="px-4 py-3">Status</th>
              <th scope="col" className="px-4 py-3 text-right">Actions</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {categories.length === 0 ? (
              <tr>
                <td colSpan={4} className="px-4 py-6 text-center text-slate-500">No categories yet.</td>
              </tr>
            ) : (
              categories.map((c) => (
                <tr key={c.id}>
                  <td className="px-4 py-3">
                    <div className="font-medium text-slate-900">{c.name}</div>
                    <div className="font-mono text-xs text-slate-500">{c.slug}</div>
                  </td>
                  <td className="px-4 py-3 text-slate-700">{c.department.name}</td>
                  <td className="px-4 py-3">
                    {c.is_active ? <StatusPill tone="success">Active</StatusPill> : <StatusPill tone="neutral">Inactive</StatusPill>}
                  </td>
                  <td className="px-4 py-3">
                    <div className="flex justify-end gap-2">
                      <Button variant="ghost" onClick={() => setEditing(c.id)} aria-label={`Edit ${c.name}`}>
                        Edit
                      </Button>
                      <Button variant="secondary" disabled={busyId === c.id} onClick={() => void toggle(c)}>
                        {c.is_active ? "Deactivate" : "Activate"}
                      </Button>
                    </div>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </Card>
  );
}

function CategoryEditor({
  category,
  departments,
  onCancel,
  onSaved,
}: {
  category?: AdminCategory;
  departments: Department[];
  onCancel: () => void;
  onSaved: (c: AdminCategory) => void;
}) {
  const [form, setForm] = useState<CategoryForm>(
    category
      ? { name: category.name, slug: category.slug, description: category.description ?? "", department_id: String(category.department.id) }
      : EMPTY_CATEGORY,
  );
  // New categories get a slug suggested from the name until the slug is edited by hand.
  const [slugTouched, setSlugTouched] = useState(Boolean(category));
  const [errors, setErrors] = useState<FieldErrors<keyof CategoryForm>>({});
  const [serverError, setServerError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const mappingChanged = category && form.department_id !== String(category.department.id);

  async function submit(event: FormEvent) {
    event.preventDefault();
    const found = validateCategoryForm(form);
    setErrors(found);
    if (Object.keys(found).length > 0) return;
    const payload = {
      name: form.name.trim(),
      slug: form.slug.trim().toLowerCase(),
      description: form.description.trim() || null,
      department_id: Number(form.department_id),
    };
    setSaving(true);
    setServerError(null);
    try {
      onSaved(category ? await updateCategory(category.id, payload) : await createCategory(payload));
    } catch (err) {
      setServerError(getErrorMessage(err));
    } finally {
      setSaving(false);
    }
  }

  return (
    <form onSubmit={submit} noValidate className="space-y-3 rounded-lg border border-slate-200 bg-slate-50 p-4" aria-label="Category form">
      <h3 className="text-sm font-semibold text-slate-900">{category ? `Edit ${category.name}` : "New category"}</h3>
      {serverError && <Alert tone="error">{serverError}</Alert>}
      <div className="grid gap-3 sm:grid-cols-3">
        <TextField
          label="Category name"
          value={form.name}
          maxLength={120}
          onChange={(e) => {
            const name = e.target.value;
            setForm((f) => ({ ...f, name, slug: slugTouched ? f.slug : slugify(name) }));
          }}
          error={errors.name}
        />
        <TextField
          label="Slug"
          value={form.slug}
          maxLength={80}
          onChange={(e) => {
            setSlugTouched(true);
            setForm((f) => ({ ...f, slug: e.target.value }));
          }}
          error={errors.slug}
        />
        <div>
          <label htmlFor="category-department" className="block text-sm font-medium text-slate-700">
            Routed to department
          </label>
          <select
            id="category-department"
            value={form.department_id}
            onChange={(e) => setForm((f) => ({ ...f, department_id: e.target.value }))}
            aria-invalid={Boolean(errors.department_id)}
            aria-describedby={errors.department_id ? "category-department-error" : undefined}
            className={`${INPUT} ${inputTone(errors.department_id)}`}
          >
            <option value="">Choose a department</option>
            {departments.map((d) => (
              <option key={d.id} value={d.id} disabled={!d.is_active}>
                {d.name}
                {d.is_active ? "" : " (inactive)"}
              </option>
            ))}
          </select>
          {errors.department_id && (
            <p id="category-department-error" className="mt-1 text-xs text-red-600">
              {errors.department_id}
            </p>
          )}
        </div>
      </div>
      {mappingChanged && <Alert tone="info">Only complaints filed after this change go to the new department.</Alert>}
      <TextArea
        label="Description (optional)"
        value={form.description}
        onChange={(value) => setForm((f) => ({ ...f, description: value }))}
        error={errors.description}
      />
      <div className="flex gap-2">
        <Button type="submit" disabled={saving}>
          {saving ? "Saving…" : category ? "Save category" : "Create category"}
        </Button>
        <Button variant="ghost" onClick={onCancel}>
          Cancel
        </Button>
      </div>
    </form>
  );
}

function TextArea({ label, value, onChange, error }: { label: string; value: string; onChange: (v: string) => void; error?: string }) {
  const id = useId();
  return (
    <div>
      <label htmlFor={id} className="block text-sm font-medium text-slate-700">
        {label}
      </label>
      <textarea
        id={id}
        rows={2}
        maxLength={1000}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        aria-invalid={Boolean(error)}
        className={`${INPUT} ${inputTone(error)}`}
      />
      {error && <p className="mt-1 text-xs text-red-600">{error}</p>}
    </div>
  );
}
