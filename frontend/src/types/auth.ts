export type UserRole = "user" | "admin" | "staff";

export interface User {
  id: number;
  full_name: string;
  email: string;
  role: UserRole;
  is_active: boolean;
  created_at: string;
  last_login_at: string | null;
  /** Set for staff (department officers) only. */
  department?: { id: number; name: string } | null;
}

export interface TokenPair {
  access_token: string;
  refresh_token: string;
  token_type: "bearer";
  expires_in: number;
}

export interface AuthResponse extends TokenPair {
  user: User;
}

export interface UserList {
  items: User[];
  total: number;
}

export interface AuditLogEntry {
  id: number;
  actor_id: number | null;
  action: string;
  target_type: string;
  target_id: string | null;
  details: Record<string, unknown> | null;
  ip_address: string | null;
  created_at: string;
}

export interface AuditLogList {
  items: AuditLogEntry[];
  total: number;
}
