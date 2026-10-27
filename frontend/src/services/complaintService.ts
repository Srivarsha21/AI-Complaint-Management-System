import type {
  Category,
  ComplaintDetail,
  ComplaintPage,
  ComplaintQuery,
  ComplaintStatus,
  NewComplaint,
} from "../types/complaint";
import { api } from "./api";

export async function listCategories(): Promise<Category[]> {
  const { data } = await api.get<Category[]>("/categories");
  return data;
}

export async function createComplaint(input: NewComplaint): Promise<ComplaintDetail> {
  const form = new FormData();
  form.append("subject", input.subject);
  form.append("description", input.description);
  form.append("category_id", String(input.category_id));
  form.append("location_text", input.location_text);
  if (input.latitude != null && input.longitude != null) {
    form.append("latitude", String(input.latitude));
    form.append("longitude", String(input.longitude));
  }
  if (input.incident_at) form.append("incident_at", input.incident_at);
  if (input.ai_category_accepted != null) form.append("ai_category_accepted", String(input.ai_category_accepted));
  input.attachments.forEach((file) => form.append("attachments", file));

  // Uploads can take longer than ordinary requests.
  const { data } = await api.post<ComplaintDetail>("/complaints", form, { timeout: 60000 });
  return data;
}

export async function listComplaints(query: ComplaintQuery): Promise<ComplaintPage> {
  const { data } = await api.get<ComplaintPage>("/complaints", {
    params: {
      status: query.status || undefined,
      category_id: query.category_id || undefined,
      search: query.search || undefined,
      sort: query.sort,
      mine: query.mine || undefined,
      limit: query.limit,
      offset: query.offset,
    },
  });
  return data;
}

export async function getComplaint(id: number): Promise<ComplaintDetail> {
  const { data } = await api.get<ComplaintDetail>(`/complaints/${id}`);
  return data;
}

export async function getComplaintByReference(reference: string): Promise<ComplaintDetail> {
  const { data } = await api.get<ComplaintDetail>(`/complaints/reference/${encodeURIComponent(reference.trim())}`);
  return data;
}

export async function addComment(id: number, body: string, isInternal = false): Promise<ComplaintDetail> {
  const { data } = await api.post<ComplaintDetail>(`/complaints/${id}/comments`, { body, is_internal: isInternal });
  return data;
}

/** Re-route (admins) and/or assign a staff member of the complaint's department. */
export async function assignComplaint(
  id: number,
  input: { department_id?: number; assignee_id?: number; note?: string },
): Promise<ComplaintDetail> {
  const { data } = await api.post<ComplaintDetail>(`/complaints/${id}/assign`, {
    department_id: input.department_id ?? null,
    assignee_id: input.assignee_id ?? null,
    note: input.note || null,
  });
  return data;
}

export async function changeStatus(id: number, status: ComplaintStatus, note?: string): Promise<ComplaintDetail> {
  const { data } = await api.post<ComplaintDetail>(`/complaints/${id}/status`, { status, note: note || null });
  return data;
}

/** Attachments need the auth header, so they are fetched as blobs rather than plain <img src>. */
export async function fetchAttachmentBlob(complaintId: number, attachmentId: number): Promise<Blob> {
  const { data } = await api.get<Blob>(`/complaints/${complaintId}/attachments/${attachmentId}`, {
    responseType: "blob",
  });
  return data;
}
