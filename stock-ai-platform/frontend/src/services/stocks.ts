import type { FundamentalReport, SectorComparison, ValuationSnapshot } from "../types/fundamentals.ts";
import type { TechnicalAnalysis } from "../types/technical.ts";
import type { HistoryResponse, MarketStatus, Quote, StockDetail, StockSearchResponse } from "../types/stock.ts";
import { apiRequest } from "./http.ts";

export function searchStocks(query: string): Promise<StockSearchResponse> {
  const params = new URLSearchParams({ q: query });
  return apiRequest<StockSearchResponse>(`/api/stocks/search?${params.toString()}`);
}

export function getStock(stockId: string): Promise<StockDetail> {
  return apiRequest<StockDetail>(`/api/stocks/${stockId}`);
}

export function getQuote(stockId: string): Promise<Quote> {
  return apiRequest<Quote>(`/api/stocks/${stockId}/quote`);
}

export function getHistory(stockId: string, range: string): Promise<HistoryResponse> {
  const params = new URLSearchParams({ range });
  return apiRequest<HistoryResponse>(`/api/stocks/${stockId}/history?${params.toString()}`);
}

export function getFundamentals(stockId: string): Promise<FundamentalReport> {
  return apiRequest<FundamentalReport>(`/api/stocks/${stockId}/fundamentals`);
}

export function getValuation(stockId: string): Promise<ValuationSnapshot> {
  return apiRequest<ValuationSnapshot>(`/api/stocks/${stockId}/valuation`);
}

export function getSectorComparison(stockId: string): Promise<SectorComparison> {
  return apiRequest<SectorComparison>(`/api/stocks/${stockId}/sector-comparison`);
}

export function getTechnicalAnalysis(stockId: string): Promise<TechnicalAnalysis> {
  return apiRequest<TechnicalAnalysis>(`/api/stocks/${stockId}/technical-analysis?interval=1d`);
}

export function getMarketStatus(exchange: string): Promise<MarketStatus> {
  return apiRequest<MarketStatus>(`/api/markets/${encodeURIComponent(exchange)}/status`);
}
