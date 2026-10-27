import type { ComplaintPriority, ComplaintStatus, NamedRef, PrioritySource } from "./complaint";

export interface Feedback {
  id: number;
  complaint_id: number;
  rating: number;
  resolved_satisfactorily: boolean;
  ai_helpful: boolean | null;
  comment: string | null;
  created_at: string;
}

export interface FeedbackInput {
  rating: number;
  resolved_satisfactorily: boolean;
  ai_helpful: boolean | null;
  comment?: string;
}

export type ReviewStatus = "unreviewed" | "correct" | "incorrect";
export type ReviewSignal = "category_changed" | "suggestion_rejected" | "priority_overridden" | "ai_not_helpful";

export interface AIReviewItem {
  prediction_id: number;
  complaint: { id: number; reference_number: string; subject: string; status: ComplaintStatus };
  final_category: NamedRef;
  predicted_category: NamedRef | null;
  category_confidence: number | null;
  user_accepted_category: boolean | null;
  predicted_priority: ComplaintPriority | null;
  final_priority: ComplaintPriority | null;
  priority_source: PrioritySource | null;
  signals: ReviewSignal[];
  review_status: ReviewStatus;
  corrected_category: NamedRef | null;
  review_note: string | null;
  reviewed_at: string | null;
  model_version: string | null;
}

export interface AIReviewPage {
  items: AIReviewItem[];
  total: number;
}

export interface QualitySummary {
  predictions: number;
  with_category_suggestion: number;
  category_agreement_rate: number | null;
  suggestion_acceptance_rate: number | null;
  priority_overrides: number;
  reviewed: number;
  marked_incorrect: number;
  feedback_count: number;
  average_rating: number | null;
  satisfied_rate: number | null;
  ai_helpful_rate: number | null;
}
