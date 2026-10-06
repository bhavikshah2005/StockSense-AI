import { useEffect, useState } from "react";
import { getHealth } from "../services/api.ts";
import type { HealthResponse } from "../types/health.ts";

export type HealthState =
  | { status: "loading" }
  | { status: "ready"; health: HealthResponse }
  | { status: "error"; message: string };

export function useHealth(): HealthState {
  const [state, setState] = useState<HealthState>({ status: "loading" });

  useEffect(() => {
    const controller = new AbortController();

    getHealth(controller.signal)
      .then((health) => {
        if (!controller.signal.aborted) {
          setState({ status: "ready", health });
        }
      })
      .catch((error: unknown) => {
        if (controller.signal.aborted) {
          return;
        }
        const message = error instanceof Error ? error.message : "Health check failed";
        setState({ status: "error", message });
      });

    return () => {
      controller.abort();
    };
  }, []);

  return state;
}
