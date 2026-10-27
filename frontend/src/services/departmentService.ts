import type { UserBrief } from "../types/complaint";
import type { AdminCategory, CategoryInput, Department, DepartmentInput } from "../types/department";
import { api } from "./api";

export async function listDepartments(): Promise<Department[]> {
  const { data } = await api.get<Department[]>("/admin/departments");
  return data;
}

export async function createDepartment(input: DepartmentInput): Promise<Department> {
  const { data } = await api.post<Department>("/admin/departments", input);
  return data;
}

export async function updateDepartment(id: number, changes: Partial<DepartmentInput>): Promise<Department> {
  const { data } = await api.patch<Department>(`/admin/departments/${id}`, changes);
  return data;
}

export async function listAdminCategories(): Promise<AdminCategory[]> {
  const { data } = await api.get<AdminCategory[]>("/admin/categories");
  return data;
}

export async function createCategory(input: CategoryInput): Promise<AdminCategory> {
  const { data } = await api.post<AdminCategory>("/admin/categories", input);
  return data;
}

export async function updateCategory(id: number, changes: Partial<CategoryInput>): Promise<AdminCategory> {
  const { data } = await api.patch<AdminCategory>(`/admin/categories/${id}`, changes);
  return data;
}

/** Active staff of a department (admins: any department; staff: their own). */
export async function listDepartmentStaff(departmentId: number): Promise<UserBrief[]> {
  const { data } = await api.get<UserBrief[]>(`/departments/${departmentId}/staff`);
  return data;
}
