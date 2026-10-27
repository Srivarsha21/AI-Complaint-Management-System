import type {
  AnalyzeRequest,
  AnalyzeResult,
  ComplaintAiAnalysis,
  ImageAnalysis,
  LanguageCode,
  TranslationResult,
} from "../types/ai";
import type { ComplaintDetail, ComplaintPriority } from "../types/complaint";
import { api } from "./api";

// --- Text analysis (module 5) ---------------------------------------------------

/** AI suggestions for a draft complaint. Nothing is stored. */
export async function analyzeComplaint(input: AnalyzeRequest): Promise<AnalyzeResult> {
  const { data } = await api.post<AnalyzeResult>("/ai/analyze", {
    subject: input.subject,
    description: input.description,
    latitude: input.latitude ?? null,
    longitude: input.longitude ?? null,
    category_id: input.category_id ?? null,
  });
  return data;
}

/** Staff only: stored prediction and similar complaints. */
export async function getComplaintAi(id: number): Promise<ComplaintAiAnalysis> {
  const { data } = await api.get<ComplaintAiAnalysis>(`/complaints/${id}/ai`);
  return data;
}

/** Staff only: set the priority (marks it as "set by staff"). */
export async function overridePriority(id: number, priority: ComplaintPriority, note?: string): Promise<ComplaintDetail> {
  const { data } = await api.patch<ComplaintDetail>(`/complaints/${id}/priority`, { priority, note: note || null });
  return data;
}

// --- Photo analysis and translation (modules 9-10) ------------------------------

/** Analyses a photo before submission. The server does not store it. */
export async function analyseImage(file: File): Promise<ImageAnalysis> {
  const form = new FormData();
  form.append("image", file);
  // The first analysis may need to load the detection model.
  const { data } = await api.post<ImageAnalysis>("/ai/image-analysis", form, { timeout: 60000 });
  return data;
}

export async function getAttachmentAnalysis(complaintId: number, attachmentId: number): Promise<ImageAnalysis> {
  const { data } = await api.get<ImageAnalysis>(`/complaints/${complaintId}/attachments/${attachmentId}/analysis`, {
    timeout: 60000,
  });
  return data;
}

export async function translateText(
  text: string,
  target: LanguageCode,
  source: LanguageCode | "auto" = "auto",
): Promise<TranslationResult> {
  const { data } = await api.post<TranslationResult>("/ai/translate", { text, source, target }, { timeout: 30000 });
  return data;
}
