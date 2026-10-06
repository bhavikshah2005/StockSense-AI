import type {
  CashMovement,
  PortfolioHistory,
  PortfolioSummary,
  PortfolioTransaction,
  RiskSettings,
  SizeResult,
  Valuation,
} from "../types/portfolio.ts";
import { apiRequest } from "./http.ts";

export function listPortfolios(): Promise<{ results: PortfolioSummary[] }> {
  return apiRequest("/api/portfolios");
}

export function createPortfolio(name: string, description: string): Promise<PortfolioSummary> {
  return apiRequest("/api/portfolios", { method: "POST", body: JSON.stringify({ name, description: description || null }) });
}

export function updatePortfolio(id: string, name: string, description: string): Promise<PortfolioSummary> {
  return apiRequest(`/api/portfolios/${id}`, { method: "PATCH", body: JSON.stringify({ name, description: description || null }) });
}

export function archivePortfolio(id: string): Promise<PortfolioSummary> {
  return apiRequest(`/api/portfolios/${id}/archive`, { method: "POST" });
}

export function deletePortfolio(id: string): Promise<void> {
  return apiRequest(`/api/portfolios/${id}`, { method: "DELETE" });
}

export function getValuation(id: string): Promise<Valuation> {
  return apiRequest(`/api/portfolios/${id}/valuation`);
}

export function getHistory(id: string): Promise<PortfolioHistory> {
  return apiRequest(`/api/portfolios/${id}/history`);
}

export function listTransactions(id: string): Promise<PortfolioTransaction[]> {
  return apiRequest(`/api/portfolios/${id}/transactions`);
}

export function createTransaction(id: string, body: Record<string, unknown>): Promise<PortfolioTransaction> {
  return apiRequest(`/api/portfolios/${id}/transactions`, { method: "POST", body: JSON.stringify(body) });
}

export function updateTransaction(id: string, transactionId: string, body: Record<string, unknown>): Promise<PortfolioTransaction> {
  return apiRequest(`/api/portfolios/${id}/transactions/${transactionId}`, { method: "PATCH", body: JSON.stringify(body) });
}

export function deleteTransaction(id: string, transactionId: string): Promise<void> {
  return apiRequest(`/api/portfolios/${id}/transactions/${transactionId}`, { method: "DELETE" });
}

export function listCash(id: string): Promise<CashMovement[]> {
  return apiRequest(`/api/portfolios/${id}/cash`);
}

export function createCash(id: string, body: Record<string, unknown>): Promise<CashMovement> {
  return apiRequest(`/api/portfolios/${id}/cash`, { method: "POST", body: JSON.stringify(body) });
}

export function getRiskSettings(): Promise<RiskSettings> {
  return apiRequest("/api/portfolios/risk-settings");
}

export function saveRiskSettings(body: RiskSettings): Promise<RiskSettings> {
  return apiRequest("/api/portfolios/risk-settings", { method: "PUT", body: JSON.stringify(body) });
}

export function calculatePositionSize(body: Record<string, unknown>): Promise<SizeResult> {
  return apiRequest("/api/portfolios/position-size", { method: "POST", body: JSON.stringify(body) });
}
