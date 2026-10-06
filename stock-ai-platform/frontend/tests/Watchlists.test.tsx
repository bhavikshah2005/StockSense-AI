import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, expect, test, vi } from "vitest";

import { WatchlistSummary } from "../src/components/dashboard/WatchlistSummary.tsx";
import { AddToWatchlist } from "../src/components/watchlist/AddToWatchlist.tsx";
import { StockSearchAdd } from "../src/components/watchlist/StockSearchAdd.tsx";
import { ApiError } from "../src/services/http.ts";
import { searchStocks } from "../src/services/stocks.ts";
import {
  addWatchlistStock,
  createWatchlist,
  deleteWatchlist,
  getWatchlist,
  listWatchlists,
  reorderWatchlist,
  removeWatchlistStock,
} from "../src/services/watchlists.ts";
import { WatchlistDetailPage } from "../src/pages/WatchlistDetailPage.tsx";
import { formatIst } from "../src/utils/quote.ts";
import { WatchlistsPage } from "../src/pages/WatchlistsPage.tsx";
import type { WatchlistDetail, WatchlistSummary as Summary } from "../src/types/watchlist.ts";

vi.mock("../src/services/watchlists.ts", () => ({
  listWatchlists: vi.fn(),
  createWatchlist: vi.fn(),
  getWatchlist: vi.fn(),
  updateWatchlist: vi.fn(),
  deleteWatchlist: vi.fn(),
  setDefaultWatchlist: vi.fn(),
  addWatchlistStock: vi.fn(),
  removeWatchlistStock: vi.fn(),
  reorderWatchlist: vi.fn(),
}));

vi.mock("../src/services/stocks.ts", () => ({
  searchStocks: vi.fn(),
}));

const unavailable = {
  available: false,
  delayed: null,
  source: null,
  currency: null,
  current_price: null,
  previous_close: null,
  change: null,
  change_percent: null,
  market_timestamp: null,
  fetched_at: null,
};

function summary(overrides: Partial<Summary> = {}): Summary {
  return {
    id: "list-1",
    name: "Core",
    description: null,
    is_default: true,
    stock_count: 0,
    contains_stock: null,
    created_at: "2026-09-24T10:00:00Z",
    updated_at: "2026-09-24T10:00:00Z",
    ...overrides,
  };
}

function detail(): WatchlistDetail {
  return {
    id: "list-1",
    name: "Core",
    description: "Daily names",
    is_default: true,
    stock_count: 2,
    created_at: "2026-09-24T10:00:00Z",
    updated_at: "2026-09-24T10:00:00Z",
    stocks: [
      {
        stock_id: "tcs",
        company_name: "Tata Consultancy Services Limited",
        symbol: "TCS",
        exchange: "NSE",
        isin: null,
        sector: "Information Technology",
        industry: null,
        sort_order: 0,
        added_at: "2026-09-24T10:05:00Z",
        quote: unavailable,
      },
      {
        stock_id: "infy",
        company_name: "Infosys Limited",
        symbol: "INFY",
        exchange: "NSE",
        isin: null,
        sector: null,
        industry: null,
        sort_order: 1,
        added_at: "2026-09-24T10:06:00Z",
        quote: {
          available: true,
          delayed: true,
          source: "yahoo",
          currency: "INR",
          current_price: "1500.00",
          previous_close: "1480.00",
          change: "20.00",
          change_percent: "1.35",
          market_timestamp: "2026-09-24T09:45:00Z",
          fetched_at: "2026-09-24T09:46:00Z",
        },
      },
    ],
  };
}

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

test("watchlist overview creates, lists, and deletes", async () => {
  vi.mocked(listWatchlists).mockResolvedValueOnce({ results: [] }).mockResolvedValue({ results: [summary({ stock_count: 1 })] });
  vi.mocked(createWatchlist).mockResolvedValue(summary({ stock_count: 1 }));
  vi.mocked(deleteWatchlist).mockResolvedValue(undefined);
  render(
    <MemoryRouter>
      <WatchlistsPage />
    </MemoryRouter>,
  );
  expect(await screen.findByText("You do not have a watchlist yet.")).toBeTruthy();
  fireEvent.click(screen.getByRole("button", { name: "Create your first watchlist" }));
  fireEvent.change(screen.getByLabelText("Name"), { target: { value: "Core" } });
  fireEvent.click(screen.getByRole("button", { name: "Save" }));
  expect(await screen.findByRole("heading", { name: /Core/ })).toBeTruthy();
  fireEvent.click(screen.getByRole("button", { name: "Delete" }));
  vi.mocked(listWatchlists).mockResolvedValueOnce({ results: [] });
  fireEvent.click(screen.getByRole("button", { name: "Confirm delete" }));
  expect(await screen.findByText("You do not have a watchlist yet.")).toBeTruthy();
});

test("watchlist overview shows a load error", async () => {
  vi.mocked(listWatchlists).mockRejectedValue(new ApiError(500, "Could not load watchlists"));
  render(
    <MemoryRouter>
      <WatchlistsPage />
    </MemoryRouter>,
  );
  expect((await screen.findByRole("alert")).textContent).toContain("Could not load watchlists");
});

test("watchlist detail reorders, removes, and keeps an unavailable quote blank", async () => {
  const body = detail();
  vi.mocked(getWatchlist).mockResolvedValue(body);
  vi.mocked(reorderWatchlist).mockResolvedValue({
    ...body,
    stocks: [body.stocks[1], body.stocks[0]],
  });
  vi.mocked(removeWatchlistStock).mockResolvedValue(undefined);
  render(
    <MemoryRouter initialEntries={["/watchlist/list-1"]}>
      <Routes>
        <Route path="/watchlist/:watchlistId" element={<WatchlistDetailPage />} />
      </Routes>
    </MemoryRouter>,
  );
  expect(await screen.findAllByText("Quote unavailable")).toHaveLength(2);
  expect(screen.getByTestId("watchlist-table")).toBeTruthy();
  expect(screen.getByTestId("watchlist-cards")).toBeTruthy();
  expect(screen.queryByText(/Delayed/)).toBeNull();
  expect(screen.queryByText(/yahoo/i)).toBeNull();
  expect(screen.getAllByText(formatIst("2026-09-24T09:46:00Z") ?? "").length).toBeGreaterThan(0);
  fireEvent.click(screen.getAllByRole("button", { name: "Move TCS down" })[0]);
  await waitFor(() => {
    expect(reorderWatchlist).toHaveBeenCalledWith("list-1", ["infy", "tcs"]);
  });
  fireEvent.click(screen.getAllByRole("button", { name: "Remove INFY" })[0]);
  await waitFor(() => {
    expect(removeWatchlistStock).toHaveBeenCalledWith("list-1", "infy");
  });
});

test("adding a stock reports a duplicate membership", async () => {
  vi.mocked(searchStocks).mockResolvedValue({
    query: "TCS",
    results: [
      {
        id: "tcs",
        symbol: "TCS",
        company_name: "Tata Consultancy Services Limited",
        exchange: "NSE",
        sector: null,
        industry: null,
        currency: "INR",
        country: "IN",
        country_name: "India",
        isin: null,
      },
    ],
  });
  render(
    <MemoryRouter>
      <StockSearchAdd watchlistId="list-1" memberIds={["tcs"]} onAdded={vi.fn()} />
    </MemoryRouter>,
  );
  fireEvent.change(screen.getByLabelText("Symbol or company"), { target: { value: "TCS" } });
  const already = await screen.findByRole("button", { name: "Already on this watchlist" });
  expect(already.hasAttribute("disabled")).toBe(true);
});

test("stock detail can add and remove a watchlist membership", async () => {
  vi.mocked(listWatchlists)
    .mockResolvedValueOnce({
      results: [summary({ contains_stock: false }), summary({ id: "list-2", name: "Ideas", is_default: false, contains_stock: true })],
    })
    .mockResolvedValue({
      results: [summary({ contains_stock: true }), summary({ id: "list-2", name: "Ideas", is_default: false, contains_stock: true })],
    });
  vi.mocked(addWatchlistStock).mockResolvedValue(detail());
  render(<AddToWatchlist stockId="tcs" />);
  fireEvent.click(screen.getByRole("button", { name: "Add to watchlist" }));
  expect(await screen.findByText("Already on this watchlist")).toBeTruthy();
  fireEvent.click(screen.getByRole("button", { name: "Add" }));
  expect((await screen.findByRole("status")).textContent).toContain("Added to watchlist");
  expect(addWatchlistStock).toHaveBeenCalledWith("list-1", "tcs");
});

test("dashboard summary links to the default watchlist and skips a missing price", async () => {
  vi.mocked(listWatchlists).mockResolvedValue({ results: [summary()] });
  vi.mocked(getWatchlist).mockResolvedValue({
    ...detail(),
    stocks: [detail().stocks[0]],
    stock_count: 1,
  });
  render(
    <MemoryRouter>
      <WatchlistSummary />
    </MemoryRouter>,
  );
  expect((await screen.findByRole("link", { name: "View watchlist" })).getAttribute("href")).toBe("/watchlist/list-1");
  expect(screen.getByText("Quote unavailable")).toBeTruthy();
  expect(screen.queryByText("₹0.00")).toBeNull();
});
