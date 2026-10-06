import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, expect, test, vi } from "vitest";

import { NotificationPopup } from "../src/components/alerts/NotificationPopup.tsx";
import { AlertsPage } from "../src/pages/AlertsPage.tsx";
import { NotificationSettings } from "../src/pages/SettingsPage.tsx";
import { ApiError } from "../src/services/http.ts";
import {
  createAlert,
  deleteAlert,
  getAlertCatalog,
  listAlerts,
  listNotifications,
  markAllNotificationsRead,
  pauseAlert,
  resumeAlert,
} from "../src/services/alerts.ts";
import { getNotificationPreferences, updateNotificationPreferences } from "../src/services/alerts.ts";

vi.mock("../src/services/alerts.ts", () => ({
  getAlertCatalog: vi.fn(),
  listAlerts: vi.fn(),
  listNotifications: vi.fn(),
  createAlert: vi.fn(),
  pauseAlert: vi.fn(),
  resumeAlert: vi.fn(),
  deleteAlert: vi.fn(),
  markAllNotificationsRead: vi.fn(),
  markNotificationRead: vi.fn(),
  getNotificationPreferences: vi.fn(),
  updateNotificationPreferences: vi.fn(),
}));

vi.mock("../src/services/stocks.ts", () => ({
  searchStocks: vi.fn(),
}));

const catalog = {
  price: { metrics: [{ key: "price", name: "Price", operators: [">", "<"], unit: "inr" }] },
  fundamental: [{ key: "pe_ratio", name: "P/E", operators: ["<="], unit: "multiple" }],
  technical: [{ key: "rsi_14", name: "RSI", operators: [">", "<"], unit: "index" }],
  pattern: { types: ["double_top"], statuses: ["confirmed"], description: "Stored detector status." },
  repeat_modes: ["once", "repeat"],
};

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

test("alerts page shows empty states", async () => {
  vi.mocked(getAlertCatalog).mockResolvedValue(catalog);
  vi.mocked(listAlerts).mockResolvedValue({ results: [], total: 0, limit: 50, offset: 0 });
  vi.mocked(listNotifications).mockResolvedValue({ results: [], total: 0, unread: 0, limit: 50, offset: 0 });
  render(
    <MemoryRouter>
      <AlertsPage />
    </MemoryRouter>,
  );
  expect(await screen.findByText("No alerts yet")).toBeTruthy();
  expect(screen.getByText("No notifications")).toBeTruthy();
});

test("alerts page shows a load error", async () => {
  vi.mocked(getAlertCatalog).mockRejectedValue(new ApiError(500, "Could not load alerts"));
  vi.mocked(listAlerts).mockRejectedValue(new ApiError(500, "Could not load alerts"));
  vi.mocked(listNotifications).mockRejectedValue(new ApiError(500, "Could not load alerts"));
  render(
    <MemoryRouter>
      <AlertsPage />
    </MemoryRouter>,
  );
  expect((await screen.findByRole("alert")).textContent).toContain("Could not load alerts");
});

test("create requires a selected stock", async () => {
  vi.mocked(getAlertCatalog).mockResolvedValue(catalog);
  vi.mocked(listAlerts).mockResolvedValue({ results: [], total: 0, limit: 50, offset: 0 });
  vi.mocked(listNotifications).mockResolvedValue({ results: [], total: 0, unread: 0, limit: 50, offset: 0 });
  render(
    <MemoryRouter>
      <AlertsPage />
    </MemoryRouter>,
  );
  fireEvent.click(await screen.findByRole("button", { name: "Save alert" }));
  expect(await screen.findByText("Choose a stock")).toBeTruthy();
  expect(createAlert).not.toHaveBeenCalled();
});

test("pause and resume call the alert service", async () => {
  vi.mocked(getAlertCatalog).mockResolvedValue(catalog);
  vi.mocked(listAlerts)
    .mockResolvedValueOnce({
      results: [
        {
          id: "a1",
          stock_id: "s1",
          symbol: "TCS",
          exchange: "NSE",
          company_name: "Tata Consultancy Services",
          category: "price",
          metric: "price",
          operator: ">",
          threshold_type: "absolute",
          threshold_value: "100",
          threshold_high: null,
          pattern_type: null,
          pattern_status: null,
          percent_interval: null,
          repeat_mode: "once",
          status: "active",
          armed: true,
          note: null,
          last_evaluated_at: null,
          last_data_status: null,
          last_value: null,
          created_at: "2026-09-24T00:00:00Z",
          updated_at: "2026-09-24T00:00:00Z",
        },
      ],
      total: 1,
      limit: 50,
      offset: 0,
    })
    .mockResolvedValue({ results: [], total: 0, limit: 50, offset: 0 });
  vi.mocked(listNotifications).mockResolvedValue({ results: [], total: 0, unread: 0, limit: 50, offset: 0 });
  vi.mocked(pauseAlert).mockResolvedValue({} as never);
  render(
    <MemoryRouter>
      <AlertsPage />
    </MemoryRouter>,
  );
  fireEvent.click(await screen.findByRole("button", { name: "Pause" }));
  expect(pauseAlert).toHaveBeenCalledWith("a1");
  expect(resumeAlert).not.toHaveBeenCalled();
  expect(deleteAlert).not.toHaveBeenCalled();
  expect(markAllNotificationsRead).not.toHaveBeenCalled();
});

test("an unread alert appears as an in-app pop-up", () => {
  const onDismiss = vi.fn();
  render(
    <MemoryRouter>
      <NotificationPopup
        note={{
          id: "n1",
          alert_id: "a1",
          stock_id: "s1",
          symbol: "TCS",
          message: "The stored close met the alert.",
          triggered_at: "2026-09-24T10:00:00Z",
          read_at: null,
          created_at: "2026-09-24T10:00:00Z",
        }}
        onDismiss={onDismiss}
      />
    </MemoryRouter>,
  );
  expect(screen.getByRole("status").textContent).toContain("TCS");
  fireEvent.click(screen.getByRole("button", { name: "Dismiss" }));
  expect(onDismiss).toHaveBeenCalledTimes(1);
});

test("notification settings stay in the app", async () => {
  vi.mocked(getNotificationPreferences).mockResolvedValue({ in_app_enabled: true });
  vi.mocked(updateNotificationPreferences).mockResolvedValue({ in_app_enabled: false });
  render(<NotificationSettings />);
  expect(await screen.findByText("Triggered alerts appear in the app.")).toBeTruthy();
  expect(screen.queryByText(/email/i)).toBeNull();
  fireEvent.click(screen.getByRole("checkbox", { name: "In-app notifications" }));
  expect(updateNotificationPreferences).toHaveBeenCalledWith(false);
});
