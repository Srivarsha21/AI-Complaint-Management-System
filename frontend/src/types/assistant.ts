export type ChannelType = "office" | "online_portal" | "helpline" | "mobile_app";
export type SourceType = "official" | "third_party";

/** A verified office or complaint channel, always with its official source. */
export interface OfficeInfo {
  id: number;
  name: string;
  organisation: string;
  channel_type: ChannelType;
  category_slugs: string[];
  address: string | null;
  locality: string | null;
  pincode: string | null;
  city: string;
  latitude: number | null;
  longitude: number | null;
  coordinates_source: string | null;
  phone: string | null;
  email: string | null;
  website: string | null;
  source_url: string;
  source_type: SourceType;
  verified_on: string;
  notes: string | null;
  distance_m: number | null;
  map_url: string | null;
  directions_url: string | null;
  osm_directions_url: string | null;
}

export interface ChatMessage {
  role: "user" | "assistant";
  content: string;
}

export type LocationInput = { latitude: number; longitude: number } | { text: string };

export interface ResolvedLocation {
  latitude: number;
  longitude: number;
  label: string | null;
  source: "device" | "geocoded";
  coordinates_source: string | null;
  in_coverage_area: boolean;
}

export interface ChatResponse {
  reply: string;
  intent: string;
  category: { id: number | null; slug: string; name: string } | null;
  needs_location: boolean;
  location: ResolvedLocation | null;
  location_status: "not_provided" | "resolved" | "not_found" | "unavailable";
  offices: OfficeInfo[];
  channels: OfficeInfo[];
  steps: string[];
  documents?: string[];
  suggestions: string[];
  disclaimer: string;
  file_complaint: { category_id: number } | null;
  generated_by: "template" | "gemini";
}
