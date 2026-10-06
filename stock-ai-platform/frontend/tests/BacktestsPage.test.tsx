import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, expect, test, vi } from "vitest";

import { BacktestDetailPage } from "../src/pages/BacktestDetailPage.tsx";
import { BacktestsPage } from "../src/pages/BacktestsPage.tsx";
import { compareRuns, createRun, deleteRun, getEquity, getRun, getTrades, listRuns, listStrategies } from "../src/services/backtests.ts";
import { searchStocks } from "../src/services/stocks.ts";
import type { BacktestRun, StrategySpec } from "../src/types/backtest.ts";

vi.mock("../src/services/backtests.ts", () => ({
  listStrategies: vi.fn(),
  listRuns: vi.fn(),
  createRun: vi.fn(),
  getRun: vi.fn(),
  getTrades: vi.fn(),
  getEquity: vi.fn(),
  deleteRun: vi.fn(),
  compareRuns: vi.fn(),
}));

vi.mock("../src/services/stocks.ts", () => ({
  searchStocks: vi.fn(),
}));

const strategy: StrategySpec = {
  key: "sma_crossover",
  version: "1",
  name: "Moving-average crossover",
  description: "Long-only test of a short simple moving average crossing a longer one.",
  holds_overnight: true,
  direction: "long_only",
  required_data: "Daily raw closes.",
  entry_rule: "Enter after the short average crosses above the long average.",
  exit_rule: "Exit when the short average falls back.",
  missing_data: "Undefined averages produce no signal.",
  parameters: [{ name: "short_period", label: "Short period", kind: "integer", minimum: 2, maximum: 100, default: 20, description: "Shorter average." }],
};

function run(status: string, summary: BacktestRun["summary"]): BacktestRun {
  return {
    id: "run-1",
    stock_id: "stock-1",
    symbol: "TCS",
    exchange: "NSE",
    strategy_key: "sma_crossover",
    strategy_version: "1",
    parameters: { short_period: 20, long_period: 50 },
    assumptions: { brokerage_percent: "0.10" },
    status,
    requested_start: "2024-03-22",
    requested_end: "2024-04-26",
    actual_start: status === "completed" ? "2024-03-22" : null,
    actual_end: status === "completed" ? "2024-04-26" : null,
    initial_capital: "100000.00",
    engine_version: "backtest-1",
    indicator_version: "indicators-1",
    detector_version: "patterns-1",
    data_source: "postgresql.stock_prices:1d",
    price_basis: "raw_close",
    summary,
    warnings: ["This is a historical simulation of one currently listed stock."],
    error_detail: status === "insufficient_data" ? "Stored daily bars do not reach the requested start." : null,
    created_at: "2026-09-25T04:00:00Z",
    started_at: "2026-09-25T04:00:00Z",
    completed_at: "2026-09-25T04:00:01Z",
  };
}

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

test("review shows the strategy rules before a run starts", async () => {
  vi.mocked(listStrategies).mockResolvedValue([strategy]);
  vi.mocked(listRuns).mockResolvedValue({ results: [], limit: 20, offset: 0 });
  vi.mocked(searchStocks).mockResolvedValue({
    query: "TCS",
    results: [{ id: "stock-1", symbol: "TCS", company_name: "Tata Consultancy Services", exchange: "NSE", sector: null, industry: null, currency: "INR", country: "IN", country_name: "India", isin: null }],
  });
  render(
    <MemoryRouter>
      <BacktestsPage />
    </MemoryRouter>,
  );
  expect(await screen.findByText(/crossing a longer one/)).toBeTruthy();
  fireEvent.change(screen.getByLabelText("Stock search"), { target: { value: "TCS" } });
  fireEvent.click(screen.getByRole("button", { name: "Search" }));
  fireEvent.click(await screen.findByRole("button", { name: /TCS · NSE/ }));
  fireEvent.change(screen.getByLabelText("Start"), { target: { value: "2024-03-22" } });
  fireEvent.change(screen.getByLabelText("End"), { target: { value: "2024-04-26" } });
  expect(await screen.findByText("Review before running")).toBeTruthy();
  expect(screen.getByText(/next stored session open/)).toBeTruthy();
  expect(createRun).not.toHaveBeenCalled();
});

test("missing history does not show trades", async () => {
  vi.mocked(getRun).mockResolvedValue(run("insufficient_data", {
    result_basis: "net",
    initial_equity: "100000.00",
    final_equity: "100000.00",
    total_return_inr: "0.00",
    total_return_percent: "0.000000",
    annualized_return_percent: null,
    annualized_return_reason: "Annualized return needs at least 252 sessions and positive ending equity.",
    max_drawdown_percent: null,
    max_drawdown_sessions: null,
    completed_trades: 0,
    winning_trades: 0,
    losing_trades: 0,
    win_rate_percent: null,
    win_rate_reason: "No completed trades.",
    average_win_inr: null,
    average_loss_inr: null,
    average_trade_return_percent: null,
    median_trade_return_percent: null,
    profit_factor: null,
    profit_factor_reason: "No completed trades.",
    exposure_percent: null,
    turnover: null,
    turnover_reason: "Average equity is not positive.",
    transaction_costs_inr: "0.00",
    sessions: 0,
    benchmark: { available: false, reason: "No historical index series is stored, so this run has no benchmark comparison." },
  }));
  vi.mocked(getTrades).mockResolvedValue({ results: [] });
  vi.mocked(getEquity).mockResolvedValue({ results: [] });
  render(
    <MemoryRouter initialEntries={["/backtests/run-1"]}>
      <Routes>
        <Route path="/backtests/:runId" element={<BacktestDetailPage />} />
      </Routes>
    </MemoryRouter>,
  );
  expect(await screen.findByText(/do not reach the requested start/)).toBeTruthy();
  expect(screen.getByText("No simulated trades were stored for this run.")).toBeTruthy();
  expect(screen.getByText(/No historical index series is stored/)).toBeTruthy();
  expect(screen.queryByText("end_of_test")).toBeNull();
});

test("a completed run shows the stored trade and equity", async () => {
  vi.mocked(getRun).mockResolvedValue(run("completed", {
    result_basis: "net",
    initial_equity: "100000.00",
    final_equity: "101000.00",
    total_return_inr: "1000.00",
    total_return_percent: "1.000000",
    annualized_return_percent: null,
    annualized_return_reason: "Annualized return needs at least 252 sessions and positive ending equity.",
    max_drawdown_percent: "1.000000",
    max_drawdown_sessions: 2,
    completed_trades: 1,
    winning_trades: 1,
    losing_trades: 0,
    win_rate_percent: "100.000000",
    win_rate_reason: null,
    average_win_inr: "1000.00",
    average_loss_inr: null,
    average_trade_return_percent: "1.000000",
    median_trade_return_percent: "1.000000",
    profit_factor: null,
    profit_factor_reason: "No losing trades, so profit factor is undefined.",
    exposure_percent: "50.000000",
    turnover: "1.000000",
    turnover_reason: null,
    transaction_costs_inr: "20.00",
    sessions: 10,
    benchmark: { available: false, reason: "No historical index series is stored, so this run has no benchmark comparison." },
  }));
  vi.mocked(getTrades).mockResolvedValue({
    results: [{
      trade_number: 1,
      signal_at: "2024-03-22T10:00:00Z",
      entry_at: "2024-03-25T10:00:00Z",
      exit_at: "2024-04-26T10:00:00Z",
      entry_price: "130.0650",
      exit_price: "129.9350",
      shares: 10,
      entry_charges: "1.30",
      exit_charges: "1.30",
      slippage_cost: "2.00",
      exit_reason: "end_of_test",
      pnl: "10.00",
      return_percent: "0.100000",
    }],
  });
  vi.mocked(getEquity).mockResolvedValue({
    results: [{ point_at: "2024-04-26T10:00:00Z", equity: "101000.00", drawdown_percent: "0.00", cash: "101000.00", shares: 0 }],
  });
  render(
    <MemoryRouter initialEntries={["/backtests/run-1"]}>
      <Routes>
        <Route path="/backtests/:runId" element={<BacktestDetailPage />} />
      </Routes>
    </MemoryRouter>,
  );
  expect(await screen.findByText("end_of_test")).toBeTruthy();
  expect(screen.getByText(/Ending equity/)).toBeTruthy();
  expect(screen.getByText(/profit factor is undefined/)).toBeTruthy();
  expect(deleteRun).not.toHaveBeenCalled();
  expect(compareRuns).not.toHaveBeenCalled();
});
