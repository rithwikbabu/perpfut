import type { DashboardOverviewResponse, RunAnalysisResponse } from "@/lib/perpfut-api";


export type MetricSeriesPoint = {
  label: string;
  value: number;
};

export type DashboardMetrics = {
  totalReturnPct: number | null;
  totalPnlUsd: number | null;
  realizedPnlUsd: number | null;
  unrealizedPnlUsd: number | null;
  maxDrawdownUsd: number | null;
  maxDrawdownPct: number | null;
  turnoverUsd: number | null;
  fillCount: number;
  tradeCount: number | null;
  avgAbsExposurePct: number | null;
  maxAbsExposurePct: number | null;
  cycleCount: number;
  equitySeries: MetricSeriesPoint[];
  drawdownSeries: MetricSeriesPoint[];
  exposureSeries: MetricSeriesPoint[];
  decisionCounts: Record<string, number>;
};

export function buildDashboardMetrics(overview: DashboardOverviewResponse): DashboardMetrics {
  return buildAnalysisMetrics(overview.latest_analysis);
}

export function buildAnalysisMetrics(
  analysis: RunAnalysisResponse | null | undefined
): DashboardMetrics {
  return {
    totalReturnPct: analysis?.total_return_pct ?? null,
    totalPnlUsd: analysis?.total_pnl_usdc ?? null,
    realizedPnlUsd: analysis?.realized_pnl_usdc ?? null,
    unrealizedPnlUsd: analysis?.unrealized_pnl_usdc ?? null,
    maxDrawdownUsd: analysis?.max_drawdown_usdc ?? null,
    maxDrawdownPct: analysis?.max_drawdown_pct ?? null,
    turnoverUsd: analysis?.turnover_usdc ?? null,
    fillCount: analysis?.fill_count ?? 0,
    tradeCount: analysis?.trade_count ?? null,
    avgAbsExposurePct: analysis?.avg_abs_exposure_pct ?? null,
    maxAbsExposurePct: analysis?.max_abs_exposure_pct ?? null,
    cycleCount: analysis?.cycle_count ?? 0,
    equitySeries: toMetricSeries(analysis?.equity_series),
    drawdownSeries: toMetricSeries(analysis?.drawdown_series),
    exposureSeries: toMetricSeries(analysis?.exposure_series),
    decisionCounts: analysis?.decision_counts ?? {},
  };
}

function toMetricSeries(
  points: { label: string; value: number }[] | null | undefined
): MetricSeriesPoint[] {
  return (points ?? []).map((point) => ({
    label: point.label,
    value: point.value,
  }));
}

export function formatMoney(value: number | null): string {
  if (value === null) {
    return "--";
  }
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
    maximumFractionDigits: 0,
  }).format(value);
}

export function formatSigned(value: number | null, digits = 2): string {
  if (value === null) {
    return "--";
  }
  return `${value > 0 ? "+" : ""}${value.toFixed(digits)}`;
}

export function formatPercent(value: number | null, digits = 2): string {
  if (value === null) {
    return "--";
  }
  return `${(value * 100).toFixed(digits)}%`;
}

export function formatSignedPercent(value: number | null, digits = 2): string {
  if (value === null) {
    return "--";
  }
  const percentage = (value * 100).toFixed(digits);
  return `${value > 0 ? "+" : ""}${percentage}%`;
}

export function formatCount(value: number | null): string {
  if (value === null) {
    return "--";
  }
  return new Intl.NumberFormat("en-US", {
    maximumFractionDigits: 0,
  }).format(value);
}

export function formatTimestamp(value: string | null): string {
  if (!value) {
    return "--";
  }
  const parsed = Date.parse(value);
  if (Number.isNaN(parsed)) {
    return value;
  }
  return new Date(parsed).toLocaleString();
}

export function formatDurationSeconds(value: number | null | undefined): string {
  if (value === null || value === undefined) {
    return "--";
  }
  const rounded = Math.max(Math.round(value), 0);
  const hours = Math.floor(rounded / 3600);
  const minutes = Math.floor((rounded % 3600) / 60);
  const seconds = rounded % 60;
  if (hours > 0) {
    return `${hours}h ${minutes}m`;
  }
  if (minutes > 0) {
    return `${minutes}m ${seconds}s`;
  }
  return `${seconds}s`;
}

export function formatSharpe(value: number | null | undefined): string {
  if (value === null || value === undefined) {
    return "--";
  }
  return value.toFixed(2);
}

export function formatDateRange(start: string | null | undefined, end: string | null | undefined): string {
  if (!start && !end) {
    return "--";
  }
  const formattedStart = formatCompactTimestamp(start);
  const formattedEnd = formatCompactTimestamp(end);
  if (formattedStart === "--") {
    return formattedEnd;
  }
  if (formattedEnd === "--") {
    return formattedStart;
  }
  return `${formattedStart} → ${formattedEnd}`;
}

function formatCompactTimestamp(value: string | null | undefined): string {
  if (!value) {
    return "--";
  }
  const parsed = Date.parse(value);
  if (Number.isNaN(parsed)) {
    return value;
  }
  return new Intl.DateTimeFormat("en-US", {
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
  }).format(new Date(parsed));
}
