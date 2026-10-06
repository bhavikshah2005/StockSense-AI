import type {
  AlertCatalog,
  AlertEventRecord,
  AlertList,
  AlertPreview,
  AlertRecord,
  NotificationList,
  NotificationPreferences,
  NotificationRecord,
} from "../types/alerts.ts";
import { apiRequest } from "./http.ts";

export type AlertDraft = {
  stock_id: string;
  category: string;
  metric: string;
  operator: string;
  threshold_type: string;
  threshold_value?: string | null;
  threshold_high?: string | null;
  pattern_type?: string | null;
  pattern_status?: string | null;
  percent_interval?: string | null;
  repeat_mode: string;
  note?: string | null;
};

export function getAlertCatalog(): Promise<AlertCatalog> {
  return apiRequest<AlertCatalog>("/api/alerts/catalog");
}

export function getAlert(id: string): Promise<AlertRecord> {
  return apiRequest<AlertRecord>(`/api/alerts/${id}`);
}

export function updateAlert(id: string, body: Partial<AlertDraft>): Promise<AlertRecord> {
  return apiRequest<AlertRecord>(`/api/alerts/${id}`, { method: "PATCH", body: JSON.stringify(body) });
}

export function listAlerts(): Promise<AlertList> {
  return apiRequest<AlertList>("/api/alerts");
}

export function createAlert(body: AlertDraft): Promise<AlertRecord> {
  return apiRequest<AlertRecord>("/api/alerts", { method: "POST", body: JSON.stringify(body) });
}

export function pauseAlert(id: string): Promise<AlertRecord> {
  return apiRequest<AlertRecord>(`/api/alerts/${id}/pause`, { method: "POST" });
}

export function resumeAlert(id: string): Promise<AlertRecord> {
  return apiRequest<AlertRecord>(`/api/alerts/${id}/resume`, { method: "POST" });
}

export function deleteAlert(id: string): Promise<void> {
  return apiRequest<void>(`/api/alerts/${id}`, { method: "DELETE" });
}

export function listAlertEvents(id: string): Promise<{ results: AlertEventRecord[]; total: number }> {
  return apiRequest(`/api/alerts/${id}/events`);
}

export function previewAlert(id: string): Promise<AlertPreview> {
  return apiRequest<AlertPreview>(`/api/alerts/${id}/preview`, { method: "POST" });
}

export function listNotifications(): Promise<NotificationList> {
  return apiRequest<NotificationList>("/api/notifications");
}

export function markNotificationRead(id: string): Promise<NotificationRecord> {
  return apiRequest<NotificationRecord>(`/api/notifications/${id}/read`, { method: "POST" });
}

export function markAllNotificationsRead(): Promise<{ updated: number }> {
  return apiRequest<{ updated: number }>("/api/notifications/read", { method: "POST" });
}

export function getNotificationPreferences(): Promise<NotificationPreferences> {
  return apiRequest<NotificationPreferences>("/api/notifications/preferences");
}

export function updateNotificationPreferences(inAppEnabled: boolean): Promise<NotificationPreferences> {
  return apiRequest<NotificationPreferences>("/api/notifications/preferences", {
    method: "PATCH",
    body: JSON.stringify({ in_app_enabled: inAppEnabled }),
  });
}
