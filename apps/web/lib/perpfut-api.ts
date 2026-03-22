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
  strategyId?: string;
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
  strategy_id: string | null;
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
  date_range_start: string | null;
  date_range_end: string | null;
  sharpe_ratio: number | null;
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

export type BacktestRunRequest = {
  productIds: string[];
  strategyIds: string[];
  start: string;
  end: string;
  granularity: "ONE_MINUTE";
  lookbackCandles?: number;
  signalScale?: number;
  startingCollateralUsdc?: number;
  maxAbsPosition?: number;
  maxGrossPosition?: number;
  maxLeverage?: number;
  slippageBps?: number;
};

export type DatasetSummaryResponse = {
  datasetId: string;
  createdAt: string;
  fingerprint: string;
  source: string;
  version: string;
  products: string[];
  start: string;
  end: string;
  granularity: string;
  candleCounts: Record<string, number>;
};

export type DatasetsListResponse = {
  items: DatasetSummaryResponse[];
  count: number;
};

export type StrategyCatalogField = {
  key: string;
  label: string;
  inputKind: "integer" | "number";
  required: boolean;
  defaultValue: number | null;
  minValue: number | null;
  maxValue: number | null;
  step: number | null;
};

export type StrategyCatalogItem = {
  strategyId: string;
  label: string;
  strategyParams: StrategyCatalogField[];
  riskOverrides: StrategyCatalogField[];
};

export type StrategyCatalogResponse = {
  items: StrategyCatalogItem[];
  count: number;
};

export type StrategyInstanceRequest = {
  strategyInstanceId: string;
  strategyId: string;
  universe: string[];
  strategyParams: Record<string, number>;
  riskOverrides: Record<string, number>;
};

export type SleeveLaunchRequest = {
  datasetId: string;
  strategyInstances: StrategyInstanceRequest[];
};

export type StrategySleeveSummary = {
  run_id: string;
  created_at: string | null;
  dataset_id: string | null;
  strategy_instance_id: string | null;
  strategy_id: string | null;
  date_range_start: string | null;
  date_range_end: string | null;
  total_pnl_usdc: number;
  total_return_pct: number;
  max_drawdown_usdc: number;
  max_drawdown_pct: number;
  avg_abs_exposure_pct: number | null;
  turnover_usdc: number | null;
};

export type StrategySleevesListResponse = {
  items: StrategySleeveSummary[];
  count: number;
};

export type StrategySleeveComparisonItem = {
  rank: number;
  run_id: string;
  dataset_id: string | null;
  strategy_instance_id: string | null;
  strategy_id: string | null;
  date_range_start: string | null;
  date_range_end: string | null;
  total_pnl_usdc: number;
  total_return_pct: number;
  max_drawdown_usdc: number;
  max_drawdown_pct: number;
  avg_abs_exposure_pct: number | null;
  turnover_usdc: number | null;
  asset_contribution_totals: Record<string, number>;
};

export type StrategySleeveComparisonResponse = {
  dataset_id: string | null;
  ranking_policy: string;
  items: StrategySleeveComparisonItem[];
};

export type StrategySleeveDetailResponse = {
  run_id: string;
  manifest: Record<string, unknown>;
  state: Record<string, unknown>;
  analysis: RunAnalysisResponse;
  sleeve_analysis: Record<string, unknown>;
};

export type PortfolioRunSummary = {
  run_id: string;
  created_at: string | null;
  dataset_id: string | null;
  date_range_start: string | null;
  date_range_end: string | null;
  sharpe_ratio: number | null;
  total_pnl_usdc: number;
  total_return_pct: number;
  max_drawdown_usdc: number;
  max_drawdown_pct: number;
  total_turnover_usdc: number;
  avg_gross_weight: number;
  max_gross_weight: number;
  strategy_instance_ids: string[];
};

export type PortfolioRunsListResponse = {
  items: PortfolioRunSummary[];
  count: number;
};

export type PortfolioContributionItem = {
  strategy_instance_id: string;
  strategy_id: string;
  sleeve_run_id: string;
  total_gross_pnl_usdc: number;
  daily_gross_pnl_series: AnalysisSeriesPoint[];
};

export type PortfolioContributionsResponse = {
  items: PortfolioContributionItem[];
  transaction_cost_total_usdc: number;
  transaction_cost_series_usdc: AnalysisSeriesPoint[];
};

export type PortfolioWeightSnapshot = {
  date: string;
  weights: Record<string, number>;
  cash_weight: number;
  turnover: number;
  gross_weight: number;
};

export type PortfolioDiagnostic = {
  date: string;
  expected_returns: Record<string, number>;
  covariance_matrix: Record<string, Record<string, number>>;
  constraint_status: string;
};

export type PortfolioRunAnalysis = {
  run_id: string;
  dataset_id: string;
  dataset_fingerprint: string;
  dataset_source: string;
  dataset_version: string;
  date_range_start: string;
  date_range_end: string;
  created_at: string;
  starting_capital_usdc: number;
  ending_equity_usdc: number;
  total_pnl_usdc: number;
  total_return_pct: number;
  sharpe_ratio: number | null;
  max_drawdown_usdc: number;
  max_drawdown_pct: number;
  total_turnover_usdc: number;
  transaction_cost_total_usdc: number;
  avg_gross_weight: number;
  max_gross_weight: number;
  strategy_instance_ids: string[];
  sleeve_run_ids: string[];
  equity_series: AnalysisSeriesPoint[];
  drawdown_series: AnalysisSeriesPoint[];
  gross_return_series: AnalysisSeriesPoint[];
  net_return_series: AnalysisSeriesPoint[];
  turnover_series_usdc: AnalysisSeriesPoint[];
  transaction_cost_series_usdc: AnalysisSeriesPoint[];
  gross_weight_series: AnalysisSeriesPoint[];
  contribution_totals_usdc: Record<string, number>;
};

export type PortfolioRunDetailResponse = {
  run_id: string;
  manifest: Record<string, unknown>;
  config: Record<string, unknown>;
  state: Record<string, unknown>;
  analysis: PortfolioRunAnalysis;
  weights: PortfolioWeightSnapshot[];
  diagnostics: PortfolioDiagnostic[];
  contributions: PortfolioContributionsResponse;
};

export type PortfolioRunComparisonItem = {
  rank: number;
  run_id: string;
  created_at: string | null;
  dataset_id: string | null;
  date_range_start: string | null;
  date_range_end: string | null;
  sharpe_ratio: number | null;
  total_pnl_usdc: number;
  total_return_pct: number;
  max_drawdown_usdc: number;
  max_drawdown_pct: number;
  total_turnover_usdc: number;
  avg_gross_weight: number;
  max_gross_weight: number;
  strategy_instance_ids: string[];
};

export type PortfolioRunComparisonResponse = {
  dataset_id: string | null;
  ranking_policy: string;
  items: PortfolioRunComparisonItem[];
};

export type BacktestJobStatusResponse = {
  job_id: string;
  status: string;
  phase: string | null;
  phase_message: string | null;
  pid: number | null;
  created_at: string;
  started_at: string | null;
  finished_at: string | null;
  total_runs: number | null;
  completed_runs: number | null;
  progress_pct: number | null;
  elapsed_seconds: number | null;
  eta_seconds: number | null;
  last_heartbeat_at: string | null;
  suite_id: string | null;
  dataset_id: string | null;
  run_ids: string[];
  error: string | null;
  log_path: string | null;
  request: BacktestRunRequest;
};

export type BacktestRunSummary = {
  run_id: string;
  created_at: string | null;
  suite_id: string | null;
  dataset_id: string | null;
  date_range_start: string | null;
  date_range_end: string | null;
  product_id: string | null;
  strategy_id: string | null;
  sharpe_ratio: number | null;
  total_pnl_usdc: number;
  total_return_pct: number;
  max_drawdown_usdc: number;
  max_drawdown_pct: number;
  turnover_usdc: number;
  fill_count: number;
  avg_abs_exposure_pct: number;
  max_abs_exposure_pct: number;
};

export type BacktestsListResponse = {
  items: BacktestRunSummary[];
  count: number;
  active_job: BacktestJobStatusResponse | null;
  latest_job: BacktestJobStatusResponse | null;
};

export type BacktestSuiteSummary = {
  suite_id: string;
  created_at: string | null;
  dataset_id: string | null;
  date_range_start: string | null;
  date_range_end: string | null;
  sharpe_ratio: number | null;
  products: string[];
  strategies: string[];
  run_ids: string[];
};

export type BacktestSuitesListResponse = {
  items: BacktestSuiteSummary[];
  count: number;
  active_job: BacktestJobStatusResponse | null;
  latest_job: BacktestJobStatusResponse | null;
};

export type BacktestSuiteComparisonItem = {
  rank: number;
  run_id: string;
  strategy_id: string | null;
  date_range_start: string | null;
  date_range_end: string | null;
  sharpe_ratio: number | null;
  total_pnl_usdc: number;
  total_return_pct: number;
  max_drawdown_usdc: number;
  max_drawdown_pct: number;
  turnover_usdc: number;
  fill_count: number;
  avg_abs_exposure_pct: number;
  max_abs_exposure_pct: number;
  decision_counts: Record<string, number>;
};

export type BacktestSuiteDetailResponse = {
  suite_id: string;
  created_at: string | null;
  dataset_id: string | null;
  date_range_start: string | null;
  date_range_end: string | null;
  sharpe_ratio: number | null;
  products: string[];
  strategies: string[];
  run_ids: string[];
  ranking_policy: string;
  items: BacktestSuiteComparisonItem[];
};

export type BacktestRunDetailResponse = {
  run_id: string;
  manifest: Record<string, unknown>;
  state: Record<string, unknown>;
  analysis: RunAnalysisResponse;
};

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

export function startBacktest(request: BacktestRunRequest): Promise<BacktestJobStatusResponse> {
  return postJson<BacktestJobStatusResponse>("/backtests", request);
}

export function launchSleeves(request: SleeveLaunchRequest): Promise<StrategySleevesListResponse> {
  return postJson<StrategySleevesListResponse>("/sleeves", request);
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
