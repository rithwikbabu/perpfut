export type RunSummary = {
  run_id: string;
  created_at: string | null;
  mode: string | null;
  product_id: string | null;
  resumed_from_run_id: string | null;
};

export type RunsListResponse = {
  items: RunSummary[];
  count: number;
};

export type DashboardOverviewResponse = {
  mode: "paper" | "live";
  generated_at: string;
  latest_run: RunSummary | null;
  latest_state: Record<string, unknown> | null;
  recent_events: Record<string, unknown>[];
  recent_fills: Record<string, unknown>[];
  recent_positions: Record<string, unknown>[];
};

export type ArtifactDocumentResponse = {
  run_id: string;
  data: Record<string, unknown>;
};

export type ArtifactListResponse = {
  run_id: string;
  items: Record<string, unknown>[];
  count: number;
};

const API_BASE = "/api/perpfut";

export async function fetchJson<T>(path: string): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    cache: "no-store",
  });
  if (!response.ok) {
    throw new Error(`API request failed: ${response.status}`);
  }
  return response.json() as Promise<T>;
}
