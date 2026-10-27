import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { vi } from "vitest";

import * as notificationService from "../services/notificationService";
import type { AppNotification } from "../types/notification";
import NotificationsPage from "./NotificationsPage";

vi.mock("../services/notificationService", async (importOriginal) => {
  const actual = await importOriginal<typeof notificationService>();
  return {
    ...actual,
    listNotifications: vi.fn(),
    markNotificationRead: vi.fn(),
    markAllNotificationsRead: vi.fn(),
  };
});

const UNREAD: AppNotification = {
  id: 2, complaint_id: 5, type: "status_changed", message: "CMP-2026-000005: status changed to Assigned.",
  is_read: false, created_at: "2026-10-10T10:00:00Z",
};
const READ: AppNotification = {
  id: 1, complaint_id: 5, type: "comment_added", message: "CMP-2026-000005: Admin One added a comment.",
  is_read: true, created_at: "2026-10-09T10:00:00Z",
};

function renderPage() {
  render(
    <MemoryRouter>
      <NotificationsPage />
    </MemoryRouter>,
  );
}

afterEach(() => vi.resetAllMocks());

test("lists notifications with unread count and links to complaints", async () => {
  vi.mocked(notificationService.listNotifications).mockResolvedValue({ items: [UNREAD, READ], total: 2, unread: 1 });
  renderPage();

  expect(await screen.findByText(UNREAD.message)).toBeInTheDocument();
  expect(screen.getByText("1 unread notification.")).toBeInTheDocument();
  const links = screen.getAllByRole("link", { name: "View complaint" });
  expect(links[0]).toHaveAttribute("href", "/app/complaints/5");
  // Only unread items offer "Mark read".
  expect(screen.getAllByRole("button", { name: /Mark as read/ })).toHaveLength(1);
});

test("marks a single notification as read and notifies the bell", async () => {
  vi.mocked(notificationService.listNotifications).mockResolvedValue({ items: [UNREAD, READ], total: 2, unread: 1 });
  vi.mocked(notificationService.markNotificationRead).mockResolvedValue({ ...UNREAD, is_read: true });
  const listener = vi.fn();
  window.addEventListener(notificationService.NOTIFICATIONS_CHANGED_EVENT, listener);
  renderPage();

  fireEvent.click(await screen.findByRole("button", { name: `Mark as read: ${UNREAD.message}` }));

  expect(await screen.findByText("You are all caught up.")).toBeInTheDocument();
  expect(notificationService.markNotificationRead).toHaveBeenCalledWith(2);
  expect(listener).toHaveBeenCalled();
  window.removeEventListener(notificationService.NOTIFICATIONS_CHANGED_EVENT, listener);
});

test("mark all as read reloads the list", async () => {
  vi.mocked(notificationService.listNotifications)
    .mockResolvedValueOnce({ items: [UNREAD, READ], total: 2, unread: 1 })
    .mockResolvedValueOnce({ items: [{ ...UNREAD, is_read: true }, READ], total: 2, unread: 0 });
  vi.mocked(notificationService.markAllNotificationsRead).mockResolvedValue(1);
  renderPage();

  fireEvent.click(await screen.findByRole("button", { name: "Mark all as read" }));

  await waitFor(() => expect(notificationService.listNotifications).toHaveBeenCalledTimes(2));
  expect(await screen.findByText("You are all caught up.")).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Mark all as read" })).toBeDisabled();
});

test("unread-only filter queries the API and shows an empty state", async () => {
  vi.mocked(notificationService.listNotifications)
    .mockResolvedValueOnce({ items: [READ], total: 1, unread: 0 })
    .mockResolvedValueOnce({ items: [], total: 0, unread: 0 });
  renderPage();
  await screen.findByText(READ.message);

  fireEvent.click(screen.getByLabelText("Unread only"));
  expect(await screen.findByText("No unread notifications.")).toBeInTheDocument();
  expect(notificationService.listNotifications).toHaveBeenLastCalledWith({ unreadOnly: true, limit: 20, offset: 0 });
  expect(within(document.body).queryByRole("link")).not.toBeInTheDocument();
});
