import type { WatchlistDetail, WatchlistListResponse, WatchlistSummary } from "../types/watchlist.ts";
import { apiRequest } from "./http.ts";

export function listWatchlists(stockId?: string): Promise<WatchlistListResponse> {
  const params = new URLSearchParams();
  if (stockId) {
    params.set("stock_id", stockId);
  }
  const query = params.toString();
  return apiRequest<WatchlistListResponse>(`/api/watchlists${query ? `?${query}` : ""}`);
}

export function createWatchlist(name: string, description: string): Promise<WatchlistSummary> {
  return apiRequest<WatchlistSummary>("/api/watchlists", {
    method: "POST",
    body: JSON.stringify({ name, description: description.trim() ? description : null }),
  });
}

export function getWatchlist(watchlistId: string): Promise<WatchlistDetail> {
  return apiRequest<WatchlistDetail>(`/api/watchlists/${watchlistId}`);
}

export function updateWatchlist(
  watchlistId: string,
  name: string,
  description: string,
): Promise<WatchlistSummary> {
  return apiRequest<WatchlistSummary>(`/api/watchlists/${watchlistId}`, {
    method: "PATCH",
    body: JSON.stringify({ name, description: description.trim() ? description : null }),
  });
}

export function deleteWatchlist(watchlistId: string): Promise<void> {
  return apiRequest<void>(`/api/watchlists/${watchlistId}`, { method: "DELETE" });
}

export function setDefaultWatchlist(watchlistId: string): Promise<WatchlistSummary> {
  return apiRequest<WatchlistSummary>(`/api/watchlists/${watchlistId}/default`, { method: "PATCH" });
}

export function addWatchlistStock(watchlistId: string, stockId: string): Promise<WatchlistDetail> {
  return apiRequest<WatchlistDetail>(`/api/watchlists/${watchlistId}/stocks`, {
    method: "POST",
    body: JSON.stringify({ stock_id: stockId }),
  });
}

export function removeWatchlistStock(watchlistId: string, stockId: string): Promise<void> {
  return apiRequest<void>(`/api/watchlists/${watchlistId}/stocks/${stockId}`, { method: "DELETE" });
}

export function reorderWatchlist(watchlistId: string, stockIds: string[]): Promise<WatchlistDetail> {
  return apiRequest<WatchlistDetail>(`/api/watchlists/${watchlistId}/stocks/order`, {
    method: "PATCH",
    body: JSON.stringify({ stock_ids: stockIds }),
  });
}
