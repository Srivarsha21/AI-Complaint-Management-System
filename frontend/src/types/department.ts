import type { NamedRef } from "./complaint";

export interface Department {
  id: number;
  name: string;
  description: string | null;
  contact_email: string | null;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface DepartmentInput {
  name: string;
  description: string | null;
  contact_email: string | null;
  is_active?: boolean;
}

export interface AdminCategory {
  id: number;
  name: string;
  slug: string;
  description: string | null;
  is_active: boolean;
  department: NamedRef;
  created_at: string;
  updated_at: string;
}

export interface CategoryInput {
  name: string;
  slug: string;
  description: string | null;
  department_id: number;
  is_active?: boolean;
}
