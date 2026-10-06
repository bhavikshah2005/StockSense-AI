import type { CompareResult, EquityPoint, BacktestRun, BacktestTrade, StrategySpec } from "../types/backtest.ts";
import { apiRequest } from "./http.ts";

export function listStrategies(): Promise<StrategySpec[]> {
  return apiRequest<StrategySpec[]>("/api/backtests/strategies");
}

export function listRuns(): Promise<{ results: BacktestRun[]; limit: number; offset: number }> {
  return apiRequest("/api/backtests/runs");
}

export function createRun(body: Record<string, unknown>): Promise<BacktestRun> {
  return apiRequest<BacktestRun>("/api/backtests/runs", { method: "POST", body: JSON.stringify(body) });
}

export function getRun(runId: string): Promise<BacktestRun> {
  return apiRequest<BacktestRun>(`/api/backtests/runs/${runId}`);
}

export function getTrades(runId: string): Promise<{ results: BacktestTrade[] }> {
  return apiRequest(`/api/backtests/runs/${runId}/trades`);
}

export function getEquity(runId: string): Promise<{ results: EquityPoint[] }> {
  return apiRequest(`/api/backtests/runs/${runId}/equity`);
}

export function deleteRun(runId: string): Promise<void> {
  return apiRequest(`/api/backtests/runs/${runId}`, { method: "DELETE" });
}

export function compareRuns(left: string, right: string): Promise<CompareResult> {
  const params = new URLSearchParams({ left, right });
  return apiRequest<CompareResult>(`/api/backtests/compare?${params.toString()}`);
}
