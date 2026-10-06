import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, expect, test, vi } from "vitest";

import { TechnicalWorkspace } from "../src/components/technical/TechnicalWorkspace.tsx";
import { ApiError } from "../src/services/http.ts";
import { getTechnicalAnalysis } from "../src/services/stocks.ts";
import type { TechnicalAnalysis } from "../src/types/technical.ts";

vi.mock("../src/services/stocks.ts", () => ({
  getTechnicalAnalysis: vi.fn(),
}));

vi.mock("../src/components/charts/TechnicalChart.tsx", () => ({
  TechnicalChart: () => <div>Chart overlays</div>,
}));

const analysis: TechnicalAnalysis = {
  stock: { id: "1", symbol: "TCS", exchange: "NSE", company_name: "Tata Consultancy Services Limited" },
  interval: "1d",
  freshness: "stale",
  price_as_of: "2026-09-01T09:45:00Z",
  calculated_at: "2026-09-24T12:00:00Z",
  indicators: {
    rsi_14: "58.000000",
    macd: "1.200000",
    macd_signal: "1.000000",
    macd_histogram: "0.200000",
    sma_20: "2000.0000",
    sma_50: "2100.0000",
    sma_100: null,
    sma_200: null,
    ema_20: "2010.0000",
    ema_50: null,
    volatility: "18.500000",
    average_volume: "1000.0000",
    volume: 1500,
    week52_high: null,
    week52_low: null,
    distance_from_high_percent: null,
    distance_from_low_percent: null,
    performance: { "1d": "1.000000" },
    as_of: "2026-09-01T09:45:00Z",
  },
  series: [{ timestamp: "2026-09-01T09:45:00Z", close: "2050.0000", sma_20: "2000.0000", sma_50: null, volume: 1500 }],
  patterns: [
    {
      pattern_type: "double_top",
      direction: "bearish_structure",
      status: "developing",
      start_timestamp: "2026-08-01T09:45:00Z",
      end_timestamp: "2026-09-01T09:45:00Z",
      levels: { neckline: "1900.0000" },
      boundaries: { neckline: [{ timestamp: "2026-09-01T09:45:00Z", price: "1900.0000" }] },
      pivots: [],
      confirmation_met: false,
      confirmation_timestamp: null,
      invalidation: "A close above the peaks invalidates the structure.",
      evidence: "Two highs within tolerance.",
      limitations: [],
      quality: "clear",
      detector_version: "patterns-1",
      definition: "Two swing highs within the level tolerance.",
    },
  ],
  zones: [
    {
      kind: "resistance",
      lower: "2040.0000",
      upper: "2060.0000",
      tests: 2,
      last_test: "2026-09-01T09:45:00Z",
      status: "active",
      method: "clustered swings",
    },
  ],
  breakouts: [],
  conclusion: {
    category: "mixed_evidence",
    text: "Recent swings conflict. This is not a forecast and it is not a trade instruction.",
    conflicts: ["RSI and MACD differ."],
    invalidation: [],
  },
  limitations: ["52-week high and low need 252 sessions."],
  indicator_version: "indicators-1",
  detector_version: "patterns-1",
};

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

test("technical workspace shows pattern evidence and overlay controls", async () => {
  vi.mocked(getTechnicalAnalysis).mockResolvedValue(analysis);
  render(<TechnicalWorkspace stockId="1" />);
  expect(await screen.findByText(/Mixed evidence/)).toBeTruthy();
  expect(screen.getByText("Developing · bearish structure · clear evidence")).toBeTruthy();
  expect(screen.getByText("Two highs within tolerance.")).toBeTruthy();
  expect(screen.getByText(/Stale prices/)).toBeTruthy();
  expect(screen.queryByText("No reliable pattern detected.")).toBeNull();
  fireEvent.click(screen.getByRole("button", { name: "Moving averages on" }));
  expect(screen.getByRole("button", { name: "Moving averages off" })).toBeTruthy();
  const text = document.body.textContent?.toLowerCase() ?? "";
  for (const banned of ["buy", "sell", "hold"]) {
    expect(new RegExp(`\\b${banned}\\b`).test(text)).toBe(false);
  }
});

test("technical workspace shows an empty pattern state", async () => {
  vi.mocked(getTechnicalAnalysis).mockResolvedValue({ ...analysis, patterns: [], freshness: "current" });
  render(<TechnicalWorkspace stockId="1" />);
  expect(await screen.findByText("No reliable pattern detected.")).toBeTruthy();
});

test("technical workspace shows a provider outage", async () => {
  vi.mocked(getTechnicalAnalysis).mockRejectedValue(new ApiError(503, "Market data service temporarily unavailable"));
  render(<TechnicalWorkspace stockId="1" />);
  expect(await screen.findByText("Price history is not available, so technical analysis cannot run.")).toBeTruthy();
});
