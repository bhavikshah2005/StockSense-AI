import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, expect, test, vi } from "vitest";

import { PortfolioDetailPage } from "../src/pages/PortfolioDetailPage.tsx";
import { PortfoliosPage } from "../src/pages/PortfoliosPage.tsx";
import { PositionSizePage } from "../src/pages/PositionSizePage.tsx";
import { ApiError } from "../src/services/http.ts";
import {
  archivePortfolio,
  calculatePositionSize,
  createPortfolio,
  deletePortfolio,
  deleteTransaction,
  getHistory,
  getRiskSettings,
  getValuation,
  listPortfolios,
  listTransactions,
  saveRiskSettings,
} from "../src/services/portfolios.ts";

vi.mock("../src/services/portfolios.ts", () => ({
  listPortfolios: vi.fn(),
  createPortfolio: vi.fn(),
  updatePortfolio: vi.fn(),
  archivePortfolio: vi.fn(),
  deletePortfolio: vi.fn(),
  getValuation: vi.fn(),
  getHistory: vi.fn(),
  listTransactions: vi.fn(),
  createTransaction: vi.fn(),
  updateTransaction: vi.fn(),
  deleteTransaction: vi.fn(),
  listCash: vi.fn(),
  createCash: vi.fn(),
  getRiskSettings: vi.fn(),
  saveRiskSettings: vi.fn(),
  calculatePositionSize: vi.fn(),
}));

const portfolio = {
  id: "p1",
  name: "Main book",
  description: "Test fixture",
  currency: "INR",
  contributed: "5000.00",
  cash: "3980.00",
  holding_count: 1,
  archived_at: null,
  created_at: "2026-09-24T04:00:00Z",
  updated_at: "2026-09-24T04:00:00Z",
};

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

test("portfolio list shows an empty state and creates a portfolio", async () => {
  vi.mocked(listPortfolios).mockResolvedValueOnce({ results: [] }).mockResolvedValueOnce({ results: [portfolio] });
  vi.mocked(createPortfolio).mockResolvedValue(portfolio);
  render(
    <MemoryRouter>
      <PortfoliosPage />
    </MemoryRouter>,
  );
  expect(await screen.findByText("You do not have a portfolio yet.")).toBeTruthy();
  fireEvent.click(screen.getByRole("button", { name: "New portfolio" }));
  fireEvent.change(screen.getByLabelText("Name"), { target: { value: "Main book" } });
  fireEvent.click(screen.getByRole("button", { name: "Save" }));
  expect(await screen.findByText("Main book")).toBeTruthy();
  expect(createPortfolio).toHaveBeenCalledWith("Main book", "");
});

test("holdings show a stale price without treating it as market value", async () => {
  vi.mocked(getValuation).mockResolvedValue({
    portfolio_id: "p1",
    currency: "INR",
    cash: "1000.00",
    contributed: "1000.00",
    cost_basis: "200.00",
    market_value: null,
    realized_pnl: "0.00",
    unrealized_pnl: null,
    total_pnl: null,
    valuation_complete: false,
    holdings_only: true,
    basis: "Total P&L is realized gain plus unrealized gain.",
    benchmark: null,
    benchmark_note: "No index series is stored, so this portfolio is not compared with a benchmark.",
    as_of: "2026-09-24T04:00:00Z",
    holdings: [
      {
        stock_id: "s1",
        symbol: "TCS",
        exchange: "NSE",
        company_name: "Tata Consultancy Services",
        sector: "Information Technology",
        quantity: "2",
        average_cost: "100.0000",
        cost_basis: "200.00",
        realized_pnl: "0.00",
        last_price: "150.00",
        market_value: null,
        unrealized_pnl: null,
        unrealized_pnl_percent: null,
        price_timestamp: "2026-08-01T04:00:00Z",
        price_state: "stale",
        delayed: true,
        delay_minutes: null,
      },
    ],
    allocation: { status: "insufficient_data", by_stock: [], by_sector: [], unpriced_symbols: ["TCS"] },
  });
  vi.mocked(getHistory).mockResolvedValue({ status: "insufficient_data", message: "Stored daily closes do not cover these holdings.", points: [] });
  vi.mocked(listTransactions).mockResolvedValue([]);
  render(
    <MemoryRouter initialEntries={["/portfolio/p1"]}>
      <Routes>
        <Route path="/portfolio/:portfolioId" element={<PortfolioDetailPage />} />
      </Routes>
    </MemoryRouter>,
  );
  expect((await screen.findAllByText(/stale/)).length).toBeGreaterThan(0);
  expect(screen.getByText("Not included")).toBeTruthy();
  expect(screen.getAllByText("Unavailable").length).toBeGreaterThan(0);
  expect(screen.getByText("Stored daily closes do not cover these holdings.")).toBeTruthy();
});

test("a failed portfolio load shows an error", async () => {
  vi.mocked(listPortfolios).mockRejectedValue(new ApiError(500, "Could not load portfolios"));
  render(
    <MemoryRouter>
      <PortfoliosPage />
    </MemoryRouter>,
  );
  expect(await screen.findByRole("alert")).toBeTruthy();
  expect(screen.getByRole("alert").textContent).toContain("Could not load portfolios");
});

test("position size shows the formula warning and a rejected scenario", async () => {
  vi.mocked(getRiskSettings).mockResolvedValue({
    capital_inr: null,
    max_risk_inr: null,
    max_risk_percent: null,
    max_allocation_percent: null,
    max_shares: null,
  });
  vi.mocked(calculatePositionSize).mockResolvedValue({
    quantity: 25,
    position_value: "2500.00",
    per_share_risk: "10.00",
    total_risk: "250.00",
    capital_utilization_percent: "25.00",
    binding_constraint: "risk",
    risk_amount: "250.00",
    assumptions: "Per-share risk is the entry price minus the stop price.",
    warning: "This quantity is not a trade instruction and is not added to a portfolio.",
  });
  render(
    <MemoryRouter>
      <PositionSizePage />
    </MemoryRouter>,
  );
  expect(await screen.findByLabelText("Entry price (INR)")).toBeTruthy();
  fireEvent.change(screen.getByLabelText("Hypothetical capital (INR)"), { target: { value: "100000" } });
  fireEvent.change(screen.getByLabelText("Entry price (INR)"), { target: { value: "100" } });
  fireEvent.change(screen.getByLabelText("Stop price (INR)"), { target: { value: "90" } });
  fireEvent.change(screen.getByLabelText("Maximum risk (INR)"), { target: { value: "250" } });
  fireEvent.click(screen.getByRole("button", { name: "Calculate" }));
  expect(await screen.findByText("25 shares")).toBeTruthy();
  expect(screen.getByText(/not a trade instruction/)).toBeTruthy();
  expect(screen.getByText(/may not execute/)).toBeTruthy();
  expect(saveRiskSettings).not.toHaveBeenCalled();
  expect(deletePortfolio).not.toHaveBeenCalled();
  expect(deleteTransaction).not.toHaveBeenCalled();
  expect(archivePortfolio).not.toHaveBeenCalled();
});
