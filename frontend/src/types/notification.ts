export interface AppNotification {
  id: number;
  complaint_id: number | null;
  type: string;
  message: string;
  is_read: boolean;
  created_at: string;
}

export interface NotificationList {
  items: AppNotification[];
  total: number;
  unread: number;
}
