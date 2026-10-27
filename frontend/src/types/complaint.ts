import type { UserRole } from "./auth";

export type ComplaintStatus = "submitted" | "assigned" | "in_progress" | "resolved" | "closed";
export type ComplaintPriority = "low" | "medium" | "high" | "critical";
/** Who set the priority: the AI prediction (module 5) or a staff member. */
export type PrioritySource = "ai" | "staff";

export interface NamedRef {
  id: number;
  name: string;
}

export interface Category {
  id: number;
  name: string;
  slug: string;
  description: string | null;
  department: NamedRef;
}

export interface UserBrief {
  id: number;
  full_name: string;
  role: UserRole;
}

export interface ComplaintListItem {
  id: number;
  reference_number: string;
  subject: string;
  status: ComplaintStatus;
  priority: ComplaintPriority | null;
  priority_source?: PrioritySource | null;
  category: NamedRef;
  department: NamedRef | null;
  location_text: string;
  user: UserBrief;
  assigned_to?: UserBrief | null;
  created_at: string;
  updated_at: string;
}

export interface StatusHistoryEntry {
  id: number;
  from_status: ComplaintStatus | null;
  to_status: ComplaintStatus;
  note: string | null;
  changed_by: UserBrief | null;
  created_at: string;
}

export interface ComplaintComment {
  id: number;
  body: string;
  is_internal: boolean;
  author: UserBrief | null;
  created_at: string;
}

export interface AssignmentEntry {
  id: number;
  from_department: NamedRef | null;
  to_department: NamedRef | null;
  assigned_to: UserBrief | null;
  assigned_by: UserBrief | null;
  note: string | null;
  created_at: string;
}

export interface Attachment {
  id: number;
  original_filename: string;
  content_type: string;
  size_bytes: number;
  created_at: string;
}

export interface ComplaintDetail extends ComplaintListItem {
  description: string;
  latitude: number | null;
  longitude: number | null;
  incident_at: string | null;
  resolved_at: string | null;
  closed_at: string | null;
  history: StatusHistoryEntry[];
  comments: ComplaintComment[];
  attachments: Attachment[];
  allowed_transitions: ComplaintStatus[];
  /** Routing history; empty unless the viewer manages the complaint. */
  assignments: AssignmentEntry[];
  /** True for admins and for staff of the complaint's department. */
  can_manage: boolean;
}

export interface ComplaintPage {
  items: ComplaintListItem[];
  total: number;
}

export interface NewComplaint {
  subject: string;
  description: string;
  category_id: number;
  location_text: string;
  latitude?: number | null;
  longitude?: number | null;
  incident_at?: string | null;
  attachments: File[];
  /** Module 5: true = kept the AI-suggested category, false = chose another, null = no suggestion. */
  ai_category_accepted?: boolean | null;
}

export interface ComplaintQuery {
  status?: ComplaintStatus | "";
  category_id?: number | "";
  search?: string;
  sort?: "newest" | "oldest" | "updated";
  mine?: boolean;
  limit: number;
  offset: number;
}
