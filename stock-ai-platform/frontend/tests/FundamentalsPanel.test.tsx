import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, expect, test, vi } from "vitest";

import { FundamentalsPanel } from "../src/components/fundamentals/FundamentalsPanel.tsx";
import { ApiError } from "../src/services/http.ts";
import { getFundamentals, getSectorComparison, getValuation } from "../src/services/stocks.ts";
import type { FundamentalReport, SectorComparison, ValuationSnapshot } from "../src/types/fundamentals.ts";
import { formatMetricValue, formatReportDay, formatSnapshotDay } from "../src/utils/fundamentals.ts";

vi.mock("../src/services/stocks.ts", () => ({
  getFundamentals: vi.fn(),
  getValuation: vi.fn(),
  getSectorComparison: vi.fn(),
}));

const emptyMetrics = {
  revenue: null,
  revenue_growth: null,
  ebitda: null,
  ebitda_growth: null,
  operating_profit: null,
  net_income: null,
  profit_growth: null,
  eps: null,
  eps_growth: null,
  book_value_per_share: null,
  roe: null,
  roce: null,
  gross_margin: null,
  operating_margin: null,
  net_margin: null,
  debt_to_equity: null,
  current_ratio: null,
  interest_coverage: null,
  free_cash_flow: null,
  operating_cash_flow: null,
  cfo_to_net_profit: null,
  revenue_cagr_3y: null,
  revenue_cagr_5y: null,
};

function report(overrides: Partial<FundamentalReport["data"]> = {}, available = true): FundamentalReport {
  return {
    stock: { id: "1", symbol: "TCS", exchange: "NSE", company_name: "Tata Consultancy Services Limited" },
    data: { ...emptyMetrics, roe: "15.00", ...overrides },
    period: { fiscal_period: "FY2026", fiscal_period_type: "annual", report_date: "2026-03-31", filing_date: "2026-05-12" },
    metadata: {
      currency: "INR",
      source: "recording",
      data_as_of: "2026-05-12T04:30:00Z",
      is_available: available,
      is_stale: true,
      filing_date_known: true,
    },
  };
}

function valuation(): ValuationSnapshot {
  return {
    stock: { id: "1", symbol: "TCS", exchange: "NSE", company_name: "Tata Consultancy Services Limited" },
    data: {
      market_price: null,
      market_cap: null,
      enterprise_value: null,
      pe_ratio: "24.50",
      pb_ratio: null,
      peg_ratio: null,
      ev_to_ebitda: null,
      ev_to_sales: null,
      dividend_yield: null,
    },
    snapshot_at: "2026-09-23T04:30:00Z",
    metadata: {
      currency: "INR",
      source: "recording",
      data_as_of: "2026-09-23T04:30:00Z",
      is_available: true,
      is_stale: false,
      filing_date_known: false,
    },
  };
}

const sector: SectorComparison = {
  stock: { id: "1", symbol: "TCS", exchange: "NSE", company_name: "Tata Consultancy Services Limited" },
  sector: "Information Technology",
  calculation_date: null,
  source: null,
  methodology: null,
  metrics: [],
  benchmark_available: false,
};

beforeEach(() => {
  vi.mocked(getFundamentals).mockReset();
  vi.mocked(getValuation).mockReset();
  vi.mocked(getSectorComparison).mockReset();
  vi.mocked(getSectorComparison).mockResolvedValue(sector);
});

afterEach(() => {
  cleanup();
});

test("shows a loading state and then reported figures", async () => {
  let resolveReport: (value: FundamentalReport) => void = () => undefined;
  vi.mocked(getFundamentals).mockReturnValue(new Promise((resolve) => {
    resolveReport = resolve;
  }));
  vi.mocked(getValuation).mockResolvedValue(valuation());
  render(<FundamentalsPanel stockId="1" />);
  expect(screen.getByText("Loading fundamentals…")).toBeTruthy();
  resolveReport(report());
  expect(await screen.findByText("ROE")).toBeTruthy();
  expect(screen.getByText("15.00%")).toBeTruthy();
  expect(screen.getByText("P/E")).toBeTruthy();
  expect(screen.getByText("Reported for FY2026")).toBeTruthy();
  expect(screen.getByText("Reported on 12 May 2026")).toBeTruthy();
  expect(screen.getByText("Valuation as of 23 Sep 2026")).toBeTruthy();
  expect(screen.getByText(/Data last updated:/)).toBeTruthy();
  expect(screen.queryByText("0.00%")).toBeNull();
});

test("omits a metric that was not supplied", async () => {
  vi.mocked(getFundamentals).mockResolvedValue(report({ roe: "15.00" }));
  vi.mocked(getValuation).mockResolvedValue(valuation());
  render(<FundamentalsPanel stockId="1" />);
  expect(await screen.findByText("ROE")).toBeTruthy();
  expect(screen.queryByText("ROCE")).toBeNull();
  expect(screen.getAllByText("Some metrics were not supplied.").length).toBeGreaterThan(0);
});

test("shows unavailable when the provider has no figures", async () => {
  vi.mocked(getFundamentals).mockResolvedValue(report({}, false));
  vi.mocked(getValuation).mockResolvedValue({
    ...valuation(),
    data: { ...valuation().data, pe_ratio: null },
    metadata: { ...valuation().metadata, is_available: false },
  });
  render(<FundamentalsPanel stockId="1" />);
  expect(await screen.findByText("Fundamental data unavailable")).toBeTruthy();
});

test("shows provider not configured and api errors", async () => {
  vi.mocked(getFundamentals).mockRejectedValue(new ApiError(503, "Fundamental data provider is not configured"));
  vi.mocked(getValuation).mockRejectedValue(new ApiError(503, "Fundamental data provider is not configured"));
  const { unmount } = render(<FundamentalsPanel stockId="1" />);
  expect(await screen.findByText("Provider not configured")).toBeTruthy();
  unmount();
  vi.mocked(getFundamentals).mockRejectedValue(new ApiError(502, "Fundamental data provider unavailable"));
  vi.mocked(getValuation).mockRejectedValue(new ApiError(502, "Fundamental data provider unavailable"));
  render(<FundamentalsPanel stockId="1" />);
  expect(await screen.findByText("Fundamental data provider unavailable")).toBeTruthy();
});

test("formats only supplied numbers", () => {
  expect(formatMetricValue("percent", null)).toBeNull();
  expect(formatMetricValue("multiple", "24.5")).toBe("24.50");
  expect(formatReportDay("2026-05-12")).toBe("12 May 2026");
  expect(formatSnapshotDay("2026-09-23T04:30:00Z")).toBe("23 Sep 2026");
});
