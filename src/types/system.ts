export type ServiceStatus = "checking" | "ready" | "unavailable";
export interface HealthResponse {
  readonly status: "ok"; readonly service: string; readonly api_version: string;
  readonly database: { readonly status: "ready"; readonly dialect: "sqlite"; readonly schema_version: string; };
  readonly pdf_engine: "weasyprint";
}
