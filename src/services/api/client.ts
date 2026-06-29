export const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://127.0.0.1:8765/api/v1";
export class ApiError extends Error { constructor(message: string, readonly status?: number) { super(message); this.name = "ApiError"; } }

interface ApiValidationDetail {
  readonly loc?: readonly (string | number)[];
  readonly msg?: string;
}

function formatApiDetail(detail: unknown): string | null {
  if (typeof detail === "string") return detail;
  if (!Array.isArray(detail)) return null;
  const messages = detail
    .map((issue) => {
      const validationIssue = issue as ApiValidationDetail;
      const location = validationIssue.loc?.filter((part) => part !== "body").join(".");
      return [location, validationIssue.msg].filter(Boolean).join(": ");
    })
    .filter(Boolean);
  return messages.length > 0 ? messages.join(" ") : null;
}

export async function apiRequest<T>(
  path: string,
  options: {
    method?: "DELETE" | "GET" | "POST" | "PUT";
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
    const body = (await response.json().catch(() => null)) as { detail?: unknown } | null;
    throw new ApiError(
      formatApiDetail(body?.detail) ?? `API request failed with status ${response.status}.`,
      response.status,
    );
  }
  if (response.status === 204) return undefined as T;
  return await response.json() as T;
}

export function apiGet<T>(path: string, options: { signal?: AbortSignal } = {}) {
  return apiRequest<T>(path, options);
}
