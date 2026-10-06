import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, expect, test, vi } from "vitest";

import { AlertDetailPage } from "../src/pages/AlertDetailPage.tsx";
import { getAlert, listAlertEvents, previewAlert, updateAlert } from "../src/services/alerts.ts";

vi.mock("../src/services/alerts.ts", () => ({
  getAlert: vi.fn(),
  listAlertEvents: vi.fn(),
  previewAlert: vi.fn(),
  updateAlert: vi.fn(),
}));

const alert = {
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
};

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

test("alert detail shows an empty history and a preview without a price", async () => {
  vi.mocked(getAlert).mockResolvedValue(alert);
  vi.mocked(listAlertEvents).mockResolvedValue({ results: [], total: 0 });
  vi.mocked(previewAlert).mockResolvedValue({
    alert_id: "a1",
    preview: true,
    state: "insufficient_data",
    explanation: "No stored daily close is available.",
    value: null,
    previous_value: null,
    reference_value: null,
    observed_at: null,
    source: "stock_prices",
    would_trigger: false,
  });
  render(
    <MemoryRouter initialEntries={["/alerts/a1"]}>
      <Routes>
        <Route path="/alerts/:alertId" element={<AlertDetailPage />} />
      </Routes>
    </MemoryRouter>,
  );
  expect(await screen.findByText("No triggers yet")).toBeTruthy();
  fireEvent.click(screen.getByRole("button", { name: "Preview current data" }));
  expect(await screen.findByText("Value unavailable")).toBeTruthy();
  expect(screen.getByText("insufficient_data")).toBeTruthy();
});

test("saving an edit sends the new threshold", async () => {
  vi.mocked(getAlert).mockResolvedValue(alert);
  vi.mocked(listAlertEvents).mockResolvedValue({ results: [], total: 0 });
  vi.mocked(updateAlert).mockResolvedValue({ ...alert, threshold_value: "120" });
  render(
    <MemoryRouter initialEntries={["/alerts/a1"]}>
      <Routes>
        <Route path="/alerts/:alertId" element={<AlertDetailPage />} />
      </Routes>
    </MemoryRouter>,
  );
  const value = await screen.findByRole("textbox", { name: "Value" });
  fireEvent.change(value, { target: { value: "120" } });
  fireEvent.click(screen.getByRole("button", { name: "Save changes" }));
  expect(updateAlert).toHaveBeenCalledWith("a1", { threshold_value: "120", note: null });
});
