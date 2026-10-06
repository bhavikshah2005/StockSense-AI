import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, expect, test, vi } from "vitest";

import { ThresholdsPage } from "../src/pages/ThresholdsPage.tsx";
import { ApiError } from "../src/services/http.ts";
import { evaluateMetrics, getMetricRegistry, listThresholds } from "../src/services/metrics.ts";
import { searchStocks } from "../src/services/stocks.ts";

vi.mock("../src/services/metrics.ts", () => ({
  getMetricRegistry: vi.fn(),
  listThresholds: vi.fn(),
  createThreshold: vi.fn(),
  updateThreshold: vi.fn(),
  deleteThreshold: vi.fn(),
  evaluateMetrics: vi.fn(),
}));

vi.mock("../src/services/stocks.ts", () => ({
  searchStocks: vi.fn(),
}));

const pe = {
  key: "pe_ratio",
  name: "P/E",
  description: "Price divided by earnings.",
  category: "fundamental" as const,
  unit: "multiple",
  operators: ["<", "between"],
  source: "valuation",
  preference: "lower",
  sector_benchmark: true,
  event_kind: null,
};

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

test("threshold page groups metrics and shows an empty state", async () => {
  vi.mocked(getMetricRegistry).mockResolvedValue({ version: "metrics-1", metrics: [pe] });
  vi.mocked(listThresholds).mockResolvedValue({ results: [] });
  render(
    <MemoryRouter>
      <ThresholdsPage />
    </MemoryRouter>,
  );
  expect(await screen.findByRole("heading", { name: "Fundamentals" })).toBeTruthy();
  expect(await screen.findByText("No threshold is configured for this metric.")).toBeTruthy();
});

test("threshold page shows a load error", async () => {
  vi.mocked(getMetricRegistry).mockRejectedValue(new ApiError(500, "Could not load metrics"));
  render(
    <MemoryRouter>
      <ThresholdsPage />
    </MemoryRouter>,
  );
  expect((await screen.findByRole("alert")).textContent).toContain("Could not load metrics");
});

test("preview renders an unavailable value without a placeholder price", async () => {
  vi.mocked(getMetricRegistry).mockResolvedValue({ version: "metrics-1", metrics: [pe] });
  vi.mocked(listThresholds).mockResolvedValue({
    results: [
      {
        id: "t1",
        metric_key: "pe_ratio",
        scope: "country",
        country: "IN",
        sector: null,
        stock_id: null,
        operator: "<=",
        basis: "absolute",
        threshold_value: "40",
        threshold_high: null,
        description: "India market default.",
        is_active: true,
        effective_from: null,
        effective_to: null,
        definition_version: "thresholds-1",
        owned: false,
        created_at: "2026-09-24T00:00:00Z",
        updated_at: "2026-09-24T00:00:00Z",
      },
    ],
  });
  vi.mocked(searchStocks).mockResolvedValue({
    query: "TCS",
    results: [
      {
        id: "tcs",
        symbol: "TCS",
        company_name: "Tata Consultancy Services Limited",
        exchange: "NSE",
        sector: "Information Technology",
        industry: null,
        currency: "INR",
        country: "IN",
        country_name: "India",
        isin: null,
      },
    ],
  });
  vi.mocked(evaluateMetrics).mockResolvedValue({
    results: [
      {
        metric_key: "pe_ratio",
        metric_name: "P/E",
        category: "fundamental",
        unit: "multiple",
        state: "insufficient_data",
        explanation: "No stored P/E value is available.",
        value: null,
        previous_value: null,
        reference_value: null,
        as_of: null,
        source: null,
        threshold: {
          id: "seed",
          scope: "market",
          operator: "<=",
          basis: "absolute",
          threshold_value: "40",
          threshold_high: null,
          definition_version: "thresholds-1",
          effective_from: null,
          reason: "Selected the market threshold.",
          skipped_scopes: [],
          user_override: false,
        },
      },
    ],
  });
  render(
    <MemoryRouter>
      <ThresholdsPage />
    </MemoryRouter>,
  );
  expect(await screen.findByText("Market IN · Less than or equal")).toBeTruthy();
  fireEvent.change(screen.getByLabelText("Symbol or company"), { target: { value: "TCS" } });
  fireEvent.click(screen.getByRole("button", { name: "Search" }));
  fireEvent.click(await screen.findByRole("button", { name: /TCS/ }));
  expect(await screen.findByText("Data unavailable")).toBeTruthy();
  expect(screen.getByText("Latest stored value: Unavailable")).toBeTruthy();
  expect(screen.queryByText("₹0.00")).toBeNull();
});
