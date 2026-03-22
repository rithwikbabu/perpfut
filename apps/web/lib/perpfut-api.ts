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

export type PaperRunRequest = {
  productId: string;
  iterations: number;
  intervalSeconds: number;
  startingCollateralUsdc: number;
};

export type PaperRunStatusResponse = {
  active: boolean;
  pid: number | null;
  started_at: string | null;
  run_id: string | null;
  product_id: string | null;
  iterations: number | null;
  interval_seconds: number | null;
  starting_collateral_usdc: number | null;
  log_path: string | null;
};

export type DashboardOverviewResponse = {
  mode: "paper" | "live";
  generated_at: string;
  latest_run: RunSummary | null;
  latest_state: Record<string, unknown> | null;
  latest_decision: LatestDecision | null;
  latest_analysis: RunAnalysis | null;
  recent_events: Record<string, unknown>[];
  recent_fills: Record<string, unknown>[];
  recent_positions: Record<string, unknown>[];
};

export type AnalysisSeriesPoint = {
  label: string;
  value: number;
};

export type RunAnalysis = {
  run_id: string;
  mode: string | null;
  product_id: string | null;
  strategy_id: string | null;
  started_at: string | null;
  ended_at: string | null;
  cycle_count: number;
  starting_equity_usdc: number;
  ending_equity_usdc: number;
  realized_pnl_usdc: number;
  unrealized_pnl_usdc: number;
  total_pnl_usdc: number;
  total_return_pct: number;
  max_drawdown_usdc: number;
  max_drawdown_pct: number;
  turnover_usdc: number;
  fill_count: number;
  trade_count: number;
  avg_abs_exposure_pct: number;
  max_abs_exposure_pct: number;
  decision_counts: Record<string, number>;
  equity_series: AnalysisSeriesPoint[];
  drawdown_series: AnalysisSeriesPoint[];
  exposure_series: AnalysisSeriesPoint[];
};

export type SignalDecision = {
  strategy: string | null;
  raw_value: number | null;
  target_position: number | null;
};

export type RiskDecision = {
  target_before_risk: number;
  target_after_risk: number;
  current_position: number;
  target_notional_usdc: number;
  current_notional_usdc: number;
  delta_notional_usdc: number;
  rebalance_threshold: number;
  min_trade_notional_usdc: number;
  halted: boolean;
  rebalance_eligible: boolean;
};

export type ExecutionSummary = {
  action: string;
  reason_code: string;
  reason_message: string;
  summary: string;
};

export type NoTradeReason = {
  code: string;
  message: string;
};

export type LatestDecision = {
  cycle_id: string | null;
  mode: string | null;
  product_id: string | null;
  signal: SignalDecision | null;
  risk_decision: RiskDecision | null;
  execution_summary: ExecutionSummary | null;
  no_trade_reason: NoTradeReason | null;
  order_intent: Record<string, unknown> | null;
  fill: Record<string, unknown> | null;
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

export type RunAnalysisResponse = RunAnalysis;

const API_BASE = "/api/perpfut";

export class ApiError extends Error {
  status: number;

  constructor(message: string, status: number) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

export async function fetchJson<T>(path: string): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    cache: "no-store",
  });
  if (!response.ok) {
    throw await buildApiError(response);
  }
  return response.json() as Promise<T>;
}

export async function postJson<T>(path: string, body?: unknown): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    method: "POST",
    cache: "no-store",
    headers: {
      "Content-Type": "application/json",
    },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  if (!response.ok) {
    throw await buildApiError(response);
  }
  return response.json() as Promise<T>;
}

export function startPaperRun(request: PaperRunRequest): Promise<PaperRunStatusResponse> {
  return postJson<PaperRunStatusResponse>("/paper-runs", request);
}

export function stopPaperRun(): Promise<PaperRunStatusResponse> {
  return postJson<PaperRunStatusResponse>("/paper-runs/stop");
}

async function buildApiError(response: Response): Promise<ApiError> {
  let detail = `API request failed: ${response.status}`;
  try {
    const payload = (await response.json()) as { detail?: string };
    if (typeof payload.detail === "string" && payload.detail) {
      detail = payload.detail;
    }
  } catch {
    // leave the fallback status message in place
  }
  return new ApiError(detail, response.status);
}
