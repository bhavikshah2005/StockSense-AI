import type { HealthResponse } from "../types/health.ts";
import { apiBaseUrl } from "../utils/env.ts";

export async function getHealth(signal?: AbortSignal): Promise<HealthResponse> {
  const response = await fetch(`${apiBaseUrl()}/health`, { signal });
  if (!response.ok) {
    throw new Error(`Health check failed with status ${response.status}`);
  }

  const body: unknown = await response.json();
  if (!isHealthResponse(body)) {
    throw new Error("Health check returned an unexpected payload");
  }
  return body;
}

function isHealthResponse(value: unknown): value is HealthResponse {
  if (typeof value !== "object" || value === null) {
    return false;
  }
  return (
    "status" in value &&
    value.status === "ok" &&
    "database" in value &&
    value.database === "ok"
  );
}
