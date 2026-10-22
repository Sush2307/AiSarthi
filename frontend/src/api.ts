import type {
  ChatResponse,
  ExplorerQuery,
  ExplorerResponse,
  Filters,
  HealthRecord,
  HealthStatus,
  Query,
  Scheme,
  Stats,
  IndicatorMeta,
  LocationMeta,
  WorkspaceCompareRequest,
  WorkspaceCompareResponse,
} from "./types";

export const API_URL: string = import.meta.env.VITE_API_URL ?? "http://localhost:8000";

async function req<T>(path: string, init?: RequestInit): Promise<T> {
  const r = await fetch(API_URL + path, { ...init, signal: init?.signal ?? AbortSignal.timeout(120000) });
  if (!r.ok) throw new Error(`Server returned ${r.status}`);
  return r.json() as Promise<T>;
}

const qs = (o: object) => {
  const p = new URLSearchParams();
  Object.entries(o).forEach(([k, v]) => v !== undefined && v !== null && v !== "" && p.set(k, String(v)));
  return p.toString();
};

export const api = {
  health: () => req<HealthStatus>("/api/health", { signal: AbortSignal.timeout(3000) }),
  chat: (question: string) =>
    req<ChatResponse>("/api/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question }),
    }),
  data: (q: Query) => req<{ count: number; records: HealthRecord[] }>("/api/health-data?" + qs(q)),
  explorer: (q: ExplorerQuery) => req<ExplorerResponse>("/api/explorer?" + qs(q)),
  workspaceCompare: (body: WorkspaceCompareRequest) =>
    req<WorkspaceCompareResponse>("/api/workspace/compare", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    }),
  workspaceIndicators: (q?: string) =>
    req<IndicatorMeta[]>("/api/workspace/indicators" + (q ? "?" + qs({ q }) : "")),
  workspaceLocations: (scope: string = "district") =>
    req<LocationMeta[]>("/api/workspace/locations?" + qs({ scope })),
  analyticsModules: () => req<any>("/api/analytics/modules"),
  stats: () => req<Stats>("/api/stats"),
  filters: (state?: string) => req<Filters>("/api/filters" + (state ? "?" + qs({ state }) : "")),
  indicators: (q?: string) => req<{ indicators: string[] }>("/api/indicators?" + qs({ q, limit: 500 })),
  schemes: () => req<{ schemes: Scheme[] }>("/api/schemes"),
  exportCsvUrl: (q: object) => `${API_URL}/api/export/csv?${qs(q)}`,
};

