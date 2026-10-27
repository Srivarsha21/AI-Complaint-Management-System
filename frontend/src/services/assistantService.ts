import type { ChatMessage, ChatResponse, LocationInput, OfficeInfo } from "../types/assistant";
import { api } from "./api";

/** The server is stateless: send the recent conversation every time. */
export const MAX_HISTORY = 20;

export async function sendChatMessage(messages: ChatMessage[], location?: LocationInput | null): Promise<ChatResponse> {
  const { data } = await api.post<ChatResponse>("/chatbot/message", {
    messages: messages.slice(-MAX_HISTORY),
    location: location ?? undefined,
  });
  return data;
}

export async function listOffices(params: { category?: string; lat?: number; lng?: number } = {}): Promise<{
  offices: OfficeInfo[];
  channels: OfficeInfo[];
}> {
  const { data } = await api.get<{ offices: OfficeInfo[]; channels: OfficeInfo[] }>("/offices", { params });
  return data;
}
