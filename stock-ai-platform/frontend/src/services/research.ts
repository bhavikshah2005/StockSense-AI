import type { ResearchList, ResearchMethodology, ResearchRun } from "../types/research.ts";
import { apiRequest } from "./http.ts";

export function getResearchMethodology(): Promise<ResearchMethodology> {
  return apiRequest<ResearchMethodology>("/api/ai/methodology");
}

export function getLatestResearch(stockId: string): Promise<ResearchRun> {
  return apiRequest<ResearchRun>(`/api/ai/stocks/${stockId}/latest`);
}

export function requestResearch(stockId: string, refresh: boolean): Promise<ResearchRun> {
  const params = new URLSearchParams({ refresh: refresh ? "true" : "false" });
  return apiRequest<ResearchRun>(`/api/ai/stocks/${stockId}/analyses?${params.toString()}`, { method: "POST" });
}

export function listResearch(stockId: string): Promise<ResearchList> {
  const params = new URLSearchParams({ stock_id: stockId, limit: "5" });
  return apiRequest<ResearchList>(`/api/ai/analyses?${params.toString()}`);
}
