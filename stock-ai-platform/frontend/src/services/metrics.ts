import type { MetricEvaluation, MetricRegistry, ThresholdRecord } from "../types/metrics.ts";
import { apiRequest } from "./http.ts";

export function getMetricRegistry(): Promise<MetricRegistry> {
  return apiRequest<MetricRegistry>("/api/metrics/registry");
}

export function listThresholds(metricKey?: string): Promise<{ results: ThresholdRecord[] }> {
  const params = new URLSearchParams();
  if (metricKey) {
    params.set("metric_key", metricKey);
  }
  const query = params.toString();
  return apiRequest<{ results: ThresholdRecord[] }>(`/api/metrics/thresholds${query ? `?${query}` : ""}`);
}

export function createThreshold(body: {
  metric_key: string;
  operator: string;
  basis: string;
  threshold_value: string | null;
  threshold_high: string | null;
  description: string | null;
}): Promise<ThresholdRecord> {
  return apiRequest<ThresholdRecord>("/api/metrics/thresholds", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export function updateThreshold(
  id: string,
  body: { is_active?: boolean; operator?: string; threshold_value?: string | null; threshold_high?: string | null; description?: string | null; basis?: string },
): Promise<ThresholdRecord> {
  return apiRequest<ThresholdRecord>(`/api/metrics/thresholds/${id}`, {
    method: "PATCH",
    body: JSON.stringify(body),
  });
}

export function deleteThreshold(id: string): Promise<void> {
  return apiRequest<void>(`/api/metrics/thresholds/${id}`, { method: "DELETE" });
}

export function evaluateMetrics(stockId: string, metricKeys: string[]): Promise<{ results: MetricEvaluation[] }> {
  return apiRequest<{ results: MetricEvaluation[] }>("/api/metrics/evaluate", {
    method: "POST",
    body: JSON.stringify({ stock_id: stockId, metric_keys: metricKeys }),
  });
}
