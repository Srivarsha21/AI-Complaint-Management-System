import type { AuditLogList, User, UserList, UserRole } from "../types/auth";
import { api } from "./api";

export interface UserQuery {
  search?: string;
  role?: UserRole | "";
  limit: number;
  offset: number;
}

export async function listUsers({ search, role, limit, offset }: UserQuery): Promise<UserList> {
  const { data } = await api.get<UserList>("/admin/users", {
    params: { search: search || undefined, role: role || undefined, limit, offset },
  });
  return data;
}

export interface UserChanges {
  role?: UserRole;
  is_active?: boolean;
  /** Required when the role becomes "staff". */
  department_id?: number;
}

export async function updateUser(userId: number, changes: UserChanges): Promise<User> {
  const { data } = await api.patch<User>(`/admin/users/${userId}`, changes);
  return data;
}

export async function listAuditLogs(limit = 50, offset = 0): Promise<AuditLogList> {
  const { data } = await api.get<AuditLogList>("/admin/audit-logs", { params: { limit, offset } });
  return data;
}
