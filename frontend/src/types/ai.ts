import type { ComplaintPriority, ComplaintStatus, NamedRef, PrioritySource } from "./complaint";

// --- Text analysis (module 5) ---------------------------------------------------

export interface CategorySuggestion {
  id: number;
  name: string;
  slug: string;
  confidence: number;
}

export interface DuplicateMatch {
  reference_number: string | null;
  status: ComplaintStatus;
  similarity: number;
  /** Only filled for staff. */
  complaint_id: number | null;
  subject: string | null;
  distance_m: number | null;
}

export interface AnalyzeRequest {
  subject: string;
  description: string;
  latitude?: number | null;
  longitude?: number | null;
  category_id?: number | null;
}

export interface AnalyzeResult {
  model_status: "ready" | "not_trained";
  category: CategorySuggestion | null;
  alternatives: CategorySuggestion[];
  department: NamedRef | null;
  priority: { level: ComplaintPriority; factors: string[] };
  sentiment: { label: "negative" | "neutral" | "positive"; score: number; urgency: number };
  possible_emergency: boolean;
  emergency_message: string | null;
  duplicates: DuplicateMatch[];
  model_version: string | null;
  disclaimer: string;
}

export interface StoredPrediction {
  predicted_category: CategorySuggestion | null;
  predicted_priority: ComplaintPriority | null;
  priority_factors: string[];
  sentiment_label: string | null;
  sentiment_score: number | null;
  urgency_score: number | null;
  possible_emergency: boolean;
  duplicate_candidates: Array<{ complaint_id: number; reference_number: string | null; status: ComplaintStatus; similarity: number }>;
  model_version: string | null;
  user_accepted_category: boolean | null;
  created_at: string;
}

export interface ComplaintAiAnalysis {
  complaint_id: number;
  prediction: StoredPrediction | null;
  priority: ComplaintPriority | null;
  priority_source: PrioritySource | null;
  similar: DuplicateMatch[];
  model_status: "ready" | "not_trained";
  disclaimer: string;
}

// --- Photo analysis and translation (modules 9-10) ------------------------------

export interface Detection {
  label: string;
  confidence: number;
  box: [number, number, number, number];
}

export interface CategoryHint {
  slug: string;
  reason: string;
}

export interface ImageAnalysis {
  valid: boolean;
  width: number;
  height: number;
  blur_score: number;
  is_blurry: boolean;
  brightness: number;
  too_dark: boolean;
  too_bright: boolean;
  detections: Detection[];
  category_hints: CategoryHint[];
  detector_available: boolean;
  model: string;
  disclaimer: string;
}

export type LanguageCode = "te" | "en";

export interface TranslationResult {
  translated_text: string;
  source_language: LanguageCode;
  target_language: LanguageCode;
  provider: "gemini";
}
