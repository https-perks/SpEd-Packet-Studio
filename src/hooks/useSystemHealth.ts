import { useEffect, useState } from "react";
import { getSystemHealth } from "../services/api/system";
import type { HealthResponse, ServiceStatus } from "../types/system";
interface State { readonly status: ServiceStatus; readonly data: HealthResponse | null; }
export function useSystemHealth(): State {
  const [state, setState] = useState<State>({ status: "checking", data: null });
  useEffect(() => { const controller = new AbortController();
    getSystemHealth(controller.signal).then((data) => setState({ status: "ready", data })).catch((error: unknown) => {
      if (error instanceof DOMException && error.name === "AbortError") return;
      setState({ status: "unavailable", data: null });
    });
    return () => controller.abort();
  }, []);
  return state;
}
