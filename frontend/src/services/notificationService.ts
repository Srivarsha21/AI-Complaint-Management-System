import type { AppNotification, NotificationList } from "../types/notification";
import { api } from "./api";

/** Fired after notifications are marked read, so the bell badge refreshes immediately. */
export const NOTIFICATIONS_CHANGED_EVENT = "resolveai:notifications-changed";

export async function listNotifications(params: { unreadOnly?: boolean; limit: number; offset: number }): Promise<NotificationList> {
  const { data } = await api.get<NotificationList>("/notifications", {
    params: { unread_only: params.unreadOnly || undefined, limit: params.limit, offset: params.offset },
  });
  return data;
}

/** Only the unread count, for the bell badge. */
export async function getUnreadCount(): Promise<number> {
  const { data } = await api.get<NotificationList>("/notifications", { params: { unread_only: true, limit: 1 } });
  return data.unread;
}

export async function markNotificationRead(id: number): Promise<AppNotification> {
  const { data } = await api.post<AppNotification>(`/notifications/${id}/read`);
  return data;
}

export async function markAllNotificationsRead(): Promise<number> {
  const { data } = await api.post<{ updated: number }>("/notifications/read-all");
  return data.updated;
}
