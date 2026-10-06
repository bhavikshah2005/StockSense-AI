import type { NewsFacets, NewsList, NewsStatus } from "../types/news.ts";
import { apiRequest } from "./http.ts";

export type NewsFilters = {
  stockId?: string;
  sector?: string;
  source?: string;
  sentiment?: string;
  windowDays?: number;
  limit?: number;
  offset?: number;
};

export function getNewsStatus(): Promise<NewsStatus> {
  return apiRequest<NewsStatus>("/api/news/status");
}

export function getNewsFacets(): Promise<NewsFacets> {
  return apiRequest<NewsFacets>("/api/news/facets");
}

export function listNews(filters: NewsFilters = {}): Promise<NewsList> {
  const params = new URLSearchParams();
  if (filters.stockId) {
    params.set("stock_id", filters.stockId);
  }
  if (filters.sector) {
    params.set("sector", filters.sector);
  }
  if (filters.source) {
    params.set("source", filters.source);
  }
  if (filters.sentiment) {
    params.set("sentiment", filters.sentiment);
  }
  if (filters.windowDays) {
    params.set("window_days", String(filters.windowDays));
  }
  params.set("limit", String(filters.limit ?? 20));
  params.set("offset", String(filters.offset ?? 0));
  return apiRequest<NewsList>(`/api/news?${params.toString()}`);
}
