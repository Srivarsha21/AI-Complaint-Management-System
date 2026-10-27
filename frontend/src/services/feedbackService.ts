import type { AIReviewItem, AIReviewPage, Feedback, FeedbackInput, QualitySummary, ReviewStatus } from "../types/feedback";
import { api } from "./api";

export async function getFeedback(complaintId: number): Promise<Feedback | null> {
  const { data } = await api.get<Feedback | null>(`/complaints/${complaintId}/feedback`);
  return data;
}

export async function submitFeedback(complaintId: number, input: FeedbackInput): Promise<Feedback> {
  const { data } = await api.post<Feedback>(`/complaints/${complaintId}/feedback`, {
    ...input,
    comment: input.comment?.trim() || null,
  });
  return data;
}

export async function listAIReviews(query: {
  review_status?: ReviewStatus | "";
  flagged_only: boolean;
  limit: number;
  offset: number;
}): Promise<AIReviewPage> {
  const { data } = await api.get<AIReviewPage>("/admin/ai-review", {
    params: { ...query, review_status: query.review_status || undefined },
  });
  return data;
}

export async function reviewPrediction(
  predictionId: number,
  input: { review_status: "correct" | "incorrect"; corrected_category_id?: number | null; note?: string },
): Promise<AIReviewItem> {
  const { data } = await api.patch<AIReviewItem>(`/admin/ai-review/${predictionId}`, {
    review_status: input.review_status,
    corrected_category_id: input.corrected_category_id ?? null,
    note: input.note?.trim() || null,
  });
  return data;
}

export async function getQualitySummary(): Promise<QualitySummary> {
  const { data } = await api.get<QualitySummary>("/admin/ai-review/summary");
  return data;
}

/** Downloads the reviewed-corrections CSV (fetched with auth, saved via an object URL). */
export async function downloadCorrections(): Promise<void> {
  const { data } = await api.get<Blob>("/admin/ai-review/corrections.csv", { responseType: "blob" });
  const url = URL.createObjectURL(data);
  const link = document.createElement("a");
  link.href = url;
  link.download = "ai-corrections.csv";
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
}
