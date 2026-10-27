/** Mirrors the backend rules for departments and categories; the backend stays authoritative. */
import { validateEmail } from "./validation";

export type FieldErrors<K extends string> = Partial<Record<K, string>>;

export interface DepartmentForm {
  name: string;
  description: string;
  contact_email: string;
}

export interface CategoryForm {
  name: string;
  slug: string;
  description: string;
  department_id: string;
}

function nameError(name: string): string | undefined {
  const cleaned = name.trim().replace(/\s+/g, " ");
  if (cleaned.length < 2) return "Name must be at least 2 characters.";
  if (cleaned.length > 120) return "Name must be at most 120 characters.";
  return undefined;
}

export function validateDepartmentForm(form: DepartmentForm): FieldErrors<keyof DepartmentForm> {
  const errors: FieldErrors<keyof DepartmentForm> = {};
  const name = nameError(form.name);
  if (name) errors.name = name;
  if (form.contact_email.trim()) {
    const email = validateEmail(form.contact_email);
    if (email) errors.contact_email = email;
  }
  if (form.description.length > 1000) errors.description = "Description must be at most 1000 characters.";
  return errors;
}

export function validateCategoryForm(form: CategoryForm): FieldErrors<keyof CategoryForm> {
  const errors: FieldErrors<keyof CategoryForm> = {};
  const name = nameError(form.name);
  if (name) errors.name = name;
  const slug = form.slug.trim().toLowerCase();
  if (!slug) errors.slug = "Slug is required.";
  else if (slug.length > 80 || !/^[a-z0-9]+(?:-[a-z0-9]+)*$/.test(slug)) {
    errors.slug = "Use lowercase letters, digits and single hyphens (e.g. street-lights).";
  }
  if (!form.department_id) errors.department_id = "Choose the department that handles this category.";
  if (form.description.length > 1000) errors.description = "Description must be at most 1000 characters.";
  return errors;
}

/** Suggests a slug from a category name, e.g. "Street Lights & Poles" -> "street-lights-poles". */
export function slugify(name: string): string {
  return name
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "")
    .slice(0, 80);
}
