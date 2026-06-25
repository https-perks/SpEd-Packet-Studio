import type { HealthResponse } from "../../types/system";
import { apiGet } from "./client";
export function getSystemHealth(signal?: AbortSignal) { return apiGet<HealthResponse>("/health", { signal }); }
