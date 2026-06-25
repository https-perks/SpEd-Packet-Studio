const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://127.0.0.1:8765/api/v1";
export class ApiError extends Error { constructor(message: string, readonly status?: number) { super(message); this.name = "ApiError"; } }
export async function apiRequest<T>(
  path: string,
  options: {
    method?: "GET" | "POST" | "PUT";
    body?: unknown;
    signal?: AbortSignal;
  } = {},
): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    method: options.method ?? "GET",
    headers: {
      Accept: "application/json",
      ...(options.body === undefined ? {} : { "Content-Type": "application/json" }),
    },
    body: options.body === undefined ? undefined : JSON.stringify(options.body),
    signal: options.signal,
  });
  if (!response.ok) {
    const body = (await response.json().catch(() => null)) as { detail?: string } | null;
    throw new ApiError(
      body?.detail ?? `API request failed with status ${response.status}.`,
      response.status,
    );
  }
  return await response.json() as T;
}

export function apiGet<T>(path: string, options: { signal?: AbortSignal } = {}) {
  return apiRequest<T>(path, options);
}
