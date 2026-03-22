"use client";

import Link from "next/link";
import { startTransition, useEffect, useState } from "react";
import {
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import useSWR from "swr";

import { ConsoleNav } from "@/components/console-nav";
import {
  formatDateRange,
  formatCount,
  formatDurationSeconds,
  formatMoney,
  formatPercent,
  formatSharpe,
  formatSignedPercent,
  formatTimestamp,
} from "@/lib/dashboard-metrics";
import {
  ApiError,
  fetchJson,
  startBacktest,
  type BacktestJobStatusResponse,
  type BacktestRunRequest,
  type BacktestsListResponse,
  type BacktestSuiteDetailResponse,
  type BacktestSuitesListResponse,
  type DatasetsListResponse,
  type PortfolioRunComparisonResponse,
  type PortfolioRunDetailResponse,
  type PortfolioRunsListResponse,
  type StrategySleeveComparisonResponse,
  type StrategySleeveDetailResponse,
  type StrategySleevesListResponse,
} from "@/lib/perpfut-api";


const PRODUCT_OPTIONS = ["BTC-PERP-INTX", "ETH-PERP-INTX", "SOL-PERP-INTX"] as const;
const STRATEGY_OPTIONS = ["momentum", "mean_reversion"] as const;

type ControlFeedback = {
  tone: "success" | "danger" | "warning";
  message: string;
};

type BacktestFormState = {
  productIds: string[];
  strategyIds: string[];
  start: string;
  end: string;
  startingCollateralUsdc: string;
  lookbackCandles: string;
  signalScale: string;
  maxAbsPosition: string;
  maxGrossPosition: string;
  maxLeverage: string;
  slippageBps: string;
};

function buildDefaultWindow() {
  const end = new Date();
  const start = new Date(end.getTime() - 24 * 60 * 60 * 1000);
  return {
    start: formatLocalDateTimeInput(start),
    end: formatLocalDateTimeInput(end),
  };
}

function buildDefaultForm(): BacktestFormState {
  const window = buildDefaultWindow();
  return {
    productIds: ["BTC-PERP-INTX", "ETH-PERP-INTX"],
    strategyIds: ["momentum", "mean_reversion"],
    start: window.start,
    end: window.end,
    startingCollateralUsdc: "10000",
    lookbackCandles: "20",
    signalScale: "12",
    maxAbsPosition: "0.5",
    maxGrossPosition: "1.0",
    maxLeverage: "2.0",
    slippageBps: "3",
  };
}

function ShellPanel({
  children,
  className = "",
}: {
  children: React.ReactNode;
  className?: string;
}) {
  return <section className={`panel ${className}`}>{children}</section>;
}

function ShellHeader({
  eyebrow,
  title,
  action,
}: {
  eyebrow: string;
  title: string;
  action?: string;
}) {
  return (
    <div className="mb-4 flex items-end justify-between gap-4">
      <div>
        <div className="mono text-[10px] uppercase tracking-[0.34em] text-[var(--accent)]">{eyebrow}</div>
        <h2 className="mt-2 text-lg font-semibold tracking-tight text-[var(--text)]">{title}</h2>
      </div>
      {action ? <div className="text-xs text-[var(--muted)]">{action}</div> : null}
    </div>
  );
}

function MetricChip({
  label,
  value,
  tone = "text",
}: {
  label: string;
  value: string;
  tone?: "accent" | "warning" | "danger" | "text";
}) {
  return (
    <div className="border border-[var(--border)] bg-[var(--bg-elevated)] px-4 py-4">
      <div className="mono text-[10px] uppercase tracking-[0.24em] text-[var(--muted)]">{label}</div>
      <div
        className={`mt-3 text-sm ${
          tone === "accent"
            ? "text-[var(--accent)]"
            : tone === "warning"
              ? "text-[var(--warning)]"
              : tone === "danger"
                ? "text-[var(--danger)]"
                : "text-[var(--text)]"
        }`}
      >
        {value}
      </div>
    </div>
  );
}

function LoadingBlock({ title }: { title: string }) {
  return (
    <div className="grid min-h-52 place-items-center border border-[var(--border)] bg-[var(--bg-elevated)] text-sm text-[var(--muted)]">
      {title}
    </div>
  );
}

function ErrorBlock({ message }: { message: string }) {
  return (
    <div className="border border-[rgba(255,109,123,0.38)] bg-[rgba(255,109,123,0.08)] p-4 text-sm leading-6 text-[var(--danger)]">
      {message}
    </div>
  );
}

function formatControlError(error: unknown): ControlFeedback {
  if (error instanceof ApiError) {
    return {
      tone: error.status === 409 ? "warning" : "danger",
      message: error.message,
    };
  }
  return {
    tone: "danger",
    message: "Unable to start the backtest suite.",
  };
}

function jobTone(status: string | null | undefined): "accent" | "warning" | "danger" | "text" {
  if (status === "running") {
    return "accent";
  }
  if (status === "succeeded") {
    return "warning";
  }
  if (status === "failed") {
    return "danger";
  }
  return "text";
}

function jobStatusLabel(status: string | null | undefined): string {
  if (!status) {
    return "idle";
  }
  return status;
}

function toggleSelection(items: string[], value: string): string[] {
  return items.includes(value) ? items.filter((item) => item !== value) : [...items, value];
}

function formatLocalDateTimeInput(value: Date): string {
  const offsetMs = value.getTimezoneOffset() * 60 * 1000;
  return new Date(value.getTime() - offsetMs).toISOString().slice(0, 16);
}

function toIsoUtc(value: string): string | null {
  if (!value.trim()) {
    return null;
  }
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) {
    return null;
  }
  return parsed.toISOString();
}

function parseOptionalNumber(value: string): number | undefined {
  if (!value.trim()) {
    return undefined;
  }
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : undefined;
}

function LaunchField({
  label,
  value,
  onChange,
  type = "text",
  step,
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
  type?: string;
  step?: string;
}) {
  return (
    <label className="block">
      <span className="mono text-[10px] uppercase tracking-[0.24em] text-[var(--muted)]">{label}</span>
      <input
        className="mt-3 w-full border border-[var(--border)] bg-[var(--bg-elevated)] px-3 py-3 text-sm text-[var(--text)] outline-none transition focus:border-[var(--border-strong)]"
        type={type}
        step={step}
        value={value}
        onChange={(event) => onChange(event.target.value)}
      />
    </label>
  );
}

function MultiSelectGrid({
  label,
  options,
  selected,
  onToggle,
}: {
  label: string;
  options: readonly string[];
  selected: string[];
  onToggle: (value: string) => void;
}) {
  return (
    <div>
      <div className="mono text-[10px] uppercase tracking-[0.24em] text-[var(--muted)]">{label}</div>
      <div className="mt-3 grid gap-2 sm:grid-cols-2">
        {options.map((option) => {
          const active = selected.includes(option);
          return (
            <button
              key={option}
              type="button"
              onClick={() => onToggle(option)}
              className={`border px-3 py-3 text-left text-sm transition ${
                active
                  ? "border-[var(--border-strong)] bg-[rgba(84,191,255,0.08)] text-[var(--text)]"
                  : "border-[var(--border)] bg-[var(--bg-elevated)] text-[var(--muted)] hover:text-[var(--text)]"
              }`}
            >
              {option}
            </button>
          );
        })}
      </div>
    </div>
  );
}

export function BacktestsShell() {
  const [form, setForm] = useState<BacktestFormState>(buildDefaultForm);
  const [feedback, setFeedback] = useState<ControlFeedback | null>(null);
  const [pendingLaunch, setPendingLaunch] = useState(false);
  const [selectedSuiteId, setSelectedSuiteId] = useState<string | null>(null);
  const [selectedDatasetId, setSelectedDatasetId] = useState<string | null>(null);
  const [selectedSleeveRunId, setSelectedSleeveRunId] = useState<string | null>(null);
  const [selectedPortfolioRunId, setSelectedPortfolioRunId] = useState<string | null>(null);

  const backtests = useSWR<BacktestsListResponse>("/backtests", fetchJson, {
    refreshInterval: 2000,
  });
  const datasets = useSWR<DatasetsListResponse>("/datasets", fetchJson, {
    refreshInterval: 2000,
  });
  const suites = useSWR<BacktestSuitesListResponse>("/backtest-suites", fetchJson, {
    refreshInterval: 2000,
  });
  const portfolioRuns = useSWR<PortfolioRunsListResponse>(
    selectedDatasetId ? `/portfolio-runs?datasetId=${encodeURIComponent(selectedDatasetId)}` : "/portfolio-runs",
    fetchJson,
    { refreshInterval: 2000 },
  );
  const portfolioComparison = useSWR<PortfolioRunComparisonResponse>(
    selectedDatasetId ? `/portfolio-run-comparisons?datasetId=${encodeURIComponent(selectedDatasetId)}` : "/portfolio-run-comparisons",
    fetchJson,
    { refreshInterval: 2000 },
  );
  const sleeves = useSWR<StrategySleevesListResponse>(
    selectedDatasetId ? `/sleeves?datasetId=${encodeURIComponent(selectedDatasetId)}` : "/sleeves",
    fetchJson,
    { refreshInterval: 2000 },
  );
  const sleeveComparison = useSWR<StrategySleeveComparisonResponse>(
    selectedDatasetId ? `/sleeve-comparisons?datasetId=${encodeURIComponent(selectedDatasetId)}` : "/sleeve-comparisons",
    fetchJson,
    { refreshInterval: 2000 },
  );
  const effectiveSelectedSleeveRunId =
    selectedSleeveRunId && sleeves.data?.items.some((item) => item.run_id === selectedSleeveRunId)
      ? selectedSleeveRunId
      : null;
  const selectedSleeve = useSWR<StrategySleeveDetailResponse>(
    effectiveSelectedSleeveRunId ? `/sleeves/${effectiveSelectedSleeveRunId}` : null,
    fetchJson,
    { refreshInterval: 2000 },
  );
  const effectiveSelectedPortfolioRunId =
    selectedPortfolioRunId && portfolioRuns.data?.items.some((item) => item.run_id === selectedPortfolioRunId)
      ? selectedPortfolioRunId
      : (portfolioRuns.data?.items[0]?.run_id ?? null);
  const selectedPortfolio = useSWR<PortfolioRunDetailResponse>(
    effectiveSelectedPortfolioRunId ? `/portfolio-runs/${effectiveSelectedPortfolioRunId}` : null,
    fetchJson,
    { refreshInterval: 2000 },
  );
  const selectedSuite = useSWR<BacktestSuiteDetailResponse>(
    selectedSuiteId ? `/backtest-suites/${selectedSuiteId}` : null,
    fetchJson,
    {
      refreshInterval: 2000,
    }
  );

  useEffect(() => {
    const nextDatasetId = datasets.data?.items[0]?.datasetId ?? null;
    if (!selectedDatasetId && nextDatasetId) {
      setSelectedDatasetId(nextDatasetId);
      return;
    }
    if (selectedDatasetId && datasets.data && !datasets.data.items.some((item) => item.datasetId === selectedDatasetId)) {
      setSelectedDatasetId(nextDatasetId);
    }
  }, [selectedDatasetId, datasets.data]);

  useEffect(() => {
    const nextSuiteId = suites.data?.items[0]?.suite_id ?? null;
    if (!selectedSuiteId && nextSuiteId) {
      setSelectedSuiteId(nextSuiteId);
      return;
    }
    if (selectedSuiteId && suites.data && !suites.data.items.some((item) => item.suite_id === selectedSuiteId)) {
      setSelectedSuiteId(nextSuiteId);
    }
  }, [selectedSuiteId, suites.data]);

  useEffect(() => {
    setSelectedSleeveRunId(null);
    setSelectedPortfolioRunId(null);
  }, [selectedDatasetId]);

  useEffect(() => {
    const nextSleeveRunId = sleeves.data?.items[0]?.run_id ?? null;
    if (!selectedSleeveRunId && nextSleeveRunId) {
      setSelectedSleeveRunId(nextSleeveRunId);
      return;
    }
    if (selectedSleeveRunId && sleeves.data && !sleeves.data.items.some((item) => item.run_id === selectedSleeveRunId)) {
      setSelectedSleeveRunId(nextSleeveRunId);
    }
  }, [selectedSleeveRunId, sleeves.data]);

  useEffect(() => {
    const nextPortfolioRunId = portfolioRuns.data?.items[0]?.run_id ?? null;
    if (!selectedPortfolioRunId && nextPortfolioRunId) {
      setSelectedPortfolioRunId(nextPortfolioRunId);
      return;
    }
    if (
      selectedPortfolioRunId &&
      portfolioRuns.data &&
      !portfolioRuns.data.items.some((item) => item.run_id === selectedPortfolioRunId)
    ) {
      setSelectedPortfolioRunId(nextPortfolioRunId);
    }
  }, [selectedPortfolioRunId, portfolioRuns.data]);

  async function refreshBacktests() {
    await Promise.all([
      backtests.mutate(),
      datasets.mutate(),
      suites.mutate(),
      portfolioRuns.mutate(),
      portfolioComparison.mutate(),
      sleeves.mutate(),
      sleeveComparison.mutate(),
      selectedSuite.mutate(),
      selectedSleeve.mutate(),
      selectedPortfolio.mutate(),
    ]);
  }

  async function handleLaunch(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (form.productIds.length === 0) {
      setFeedback({ tone: "warning", message: "Select at least one product." });
      return;
    }
    if (form.strategyIds.length === 0) {
      setFeedback({ tone: "warning", message: "Select at least one strategy." });
      return;
    }
    const startIso = toIsoUtc(form.start);
    const endIso = toIsoUtc(form.end);
    if (!startIso || !endIso) {
      setFeedback({ tone: "warning", message: "Provide both start and end datetimes." });
      return;
    }

    const request: BacktestRunRequest = {
      productIds: form.productIds,
      strategyIds: form.strategyIds,
      start: startIso,
      end: endIso,
      granularity: "ONE_MINUTE",
      startingCollateralUsdc: parseOptionalNumber(form.startingCollateralUsdc),
      lookbackCandles: parseOptionalNumber(form.lookbackCandles),
      signalScale: parseOptionalNumber(form.signalScale),
      maxAbsPosition: parseOptionalNumber(form.maxAbsPosition),
      maxGrossPosition: parseOptionalNumber(form.maxGrossPosition),
      maxLeverage: parseOptionalNumber(form.maxLeverage),
      slippageBps: parseOptionalNumber(form.slippageBps),
    };

    setPendingLaunch(true);
    setFeedback(null);
    try {
      const job = await startBacktest(request);
      setFeedback({
        tone: "success",
        message: `Backtest job ${job.job_id} started for ${job.request.strategyIds.join(", ")}.`,
      });
      await refreshBacktests();
    } catch (error) {
      setFeedback(formatControlError(error));
      await refreshBacktests();
    } finally {
      setPendingLaunch(false);
    }
  }

  const activeJob =
    backtests.data?.active_job ??
    suites.data?.active_job ??
    backtests.data?.latest_job ??
    suites.data?.latest_job ??
    null;
  const latestSuite = suites.data?.items[0] ?? null;
  const selectedDataset =
    datasets.data?.items.find((item) => item.datasetId === selectedDatasetId) ??
    datasets.data?.items[0] ??
    null;
  const hasConsoleError = backtests.error || suites.error;

  return (
    <main className="min-h-screen px-4 py-4 text-[var(--text)] sm:px-6 lg:px-8">
      <div className="mx-auto grid max-w-[1680px] gap-4 lg:grid-cols-[260px_minmax(0,1fr)]">
        <aside className="panel flex min-h-[calc(100vh-2rem)] flex-col justify-between p-5">
          <div>
            <div className="mono text-[11px] uppercase tracking-[0.34em] text-[var(--accent)]">perpfut</div>
            <div className="mt-3 text-2xl font-semibold tracking-tight">Backtest Console</div>
            <p className="mt-3 max-w-xs text-sm leading-6 text-[var(--muted)]">
              Historical strategy evaluation with shared production strategy code, artifact-backed datasets,
              and suite comparisons.
            </p>
            <ConsoleNav active="backtests" />
          </div>

          <div className="space-y-4">
            <div className="border border-[var(--border)] bg-[var(--bg-elevated)] p-4">
              <div className="mono text-[10px] uppercase tracking-[0.28em] text-[var(--warning)]">
                Backtest Status
              </div>
              <div
                className={`mt-3 text-sm ${
                  jobTone(activeJob?.status) === "accent"
                    ? "text-[var(--accent)]"
                    : jobTone(activeJob?.status) === "warning"
                      ? "text-[var(--warning)]"
                      : jobTone(activeJob?.status) === "danger"
                        ? "text-[var(--danger)]"
                        : "text-[var(--text)]"
                }`}
              >
                {activeJob ? `${jobStatusLabel(activeJob.status).toUpperCase()} · ${activeJob.job_id}` : "No recent backtest job"}
              </div>
              <p className="mt-2 text-sm leading-6 text-[var(--muted)]">
                {activeJob
                  ? activeJob.phase_message ??
                    `${activeJob.request.productIds.join(", ")} · ${activeJob.request.strategyIds.join(", ")}`
                  : "Launch a suite to populate the shared historical backtest queue."}
              </p>
            </div>

            <div className="border border-[var(--border)] bg-[var(--bg-elevated)] p-4">
              <div className="mono text-[10px] uppercase tracking-[0.28em] text-[var(--warning)]">
                Selected Dataset
              </div>
              {datasets.isLoading ? (
                <p className="mt-3 text-sm leading-6 text-[var(--muted)]">Loading cached datasets.</p>
              ) : datasets.error ? (
                <p className="mt-3 text-sm leading-6 text-[var(--danger)]">{datasets.error.message}</p>
              ) : selectedDataset ? (
                <>
                  <div className="mt-3 text-sm text-[var(--text)]">{selectedDataset.datasetId}</div>
                  <p className="mt-2 text-sm leading-6 text-[var(--muted)]">
                    {selectedDataset.products.join(", ")} · {selectedDataset.source} · fp {selectedDataset.fingerprint.slice(0, 10)}
                  </p>
                  <div className="mt-3 grid gap-2 sm:grid-cols-2">
                    <MetricChip
                      label="Coverage"
                      value={formatDateRange(selectedDataset.start, selectedDataset.end)}
                    />
                    <MetricChip label="Status" value="cached" />
                  </div>
                </>
              ) : (
                <p className="mt-3 text-sm leading-6 text-[var(--muted)]">
                  No cached datasets yet.
                </p>
              )}
            </div>
          </div>
        </aside>

        <section className="space-y-4">
          <header className="panel panel-strong flex flex-col gap-5 p-5 lg:flex-row lg:items-end lg:justify-between">
            <div>
              <div className="mono text-[11px] uppercase tracking-[0.34em] text-[var(--accent)]">
                Historical Console
              </div>
              <h1 className="mt-3 max-w-3xl text-3xl font-semibold tracking-tight">
                Launch and rank historical strategy suites.
              </h1>
              <p className="mt-3 max-w-3xl text-sm leading-6 text-[var(--muted)]">
                This console launches local backtest jobs, lists completed backtest runs, and ranks strategy
                suites on the same canonical metrics contract used elsewhere in the repo.
              </p>
            </div>
            <div className="grid gap-2 text-xs uppercase tracking-[0.22em] text-[var(--muted)] sm:grid-cols-3">
              <div className="border border-[var(--border)] px-3 py-3">
                <div className="mono text-[10px] text-[var(--accent)]">Source</div>
                <div className="mt-2 text-sm text-[var(--text)]">Coinbase Candles</div>
              </div>
              <div className="border border-[var(--border)] px-3 py-3">
                <div className="mono text-[10px] text-[var(--accent)]">Execution</div>
                <div className="mt-2 text-sm text-[var(--text)]">Next Open</div>
              </div>
              <div className="border border-[var(--border)] px-3 py-3">
                <div className="mono text-[10px] text-[var(--accent)]">Queue</div>
                <div className="mt-2 text-sm text-[var(--text)]">
                  {activeJob?.status === "running" ? "1 active" : activeJob ? activeJob.status : "idle"}
                </div>
              </div>
            </div>
          </header>

          {hasConsoleError ? (
            <ShellPanel className="p-5">
              <ShellHeader eyebrow="Connection" title="Backtest API unavailable" />
              <ErrorBlock message={(backtests.error ?? suites.error ?? new Error("unknown")).message} />
            </ShellPanel>
          ) : null}

          {feedback ? (
            <ShellPanel className="p-5">
              <div
                className={`border p-4 text-sm leading-6 ${
                  feedback.tone === "success"
                    ? "border-[rgba(143,214,255,0.36)] bg-[rgba(143,214,255,0.08)] text-[var(--accent)]"
                    : feedback.tone === "warning"
                      ? "border-[rgba(241,187,103,0.36)] bg-[rgba(241,187,103,0.08)] text-[var(--warning)]"
                      : "border-[rgba(255,109,123,0.38)] bg-[rgba(255,109,123,0.08)] text-[var(--danger)]"
                }`}
              >
                {feedback.message}
              </div>
            </ShellPanel>
          ) : null}

          <div className="grid gap-4 xl:grid-cols-[1.05fr_0.95fr]">
            <ShellPanel className="p-5">
              <ShellHeader eyebrow="Launch" title="Start a backtest suite" action="POST /api/backtests" />
              <form className="space-y-5" onSubmit={handleLaunch}>
                <MultiSelectGrid
                  label="Products"
                  options={PRODUCT_OPTIONS}
                  selected={form.productIds}
                  onToggle={(value) => setForm((current) => ({ ...current, productIds: toggleSelection(current.productIds, value) }))}
                />
                <MultiSelectGrid
                  label="Strategies"
                  options={STRATEGY_OPTIONS}
                  selected={form.strategyIds}
                  onToggle={(value) =>
                    setForm((current) => ({ ...current, strategyIds: toggleSelection(current.strategyIds, value) }))
                  }
                />

                <div className="grid gap-4 md:grid-cols-2">
                  <LaunchField
                    label="Start"
                    type="datetime-local"
                    value={form.start}
                    onChange={(value) => setForm((current) => ({ ...current, start: value }))}
                  />
                  <LaunchField
                    label="End"
                    type="datetime-local"
                    value={form.end}
                    onChange={(value) => setForm((current) => ({ ...current, end: value }))}
                  />
                </div>

                <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
                  <LaunchField
                    label="Starting Capital"
                    type="number"
                    step="100"
                    value={form.startingCollateralUsdc}
                    onChange={(value) => setForm((current) => ({ ...current, startingCollateralUsdc: value }))}
                  />
                  <LaunchField
                    label="Lookback Candles"
                    type="number"
                    step="1"
                    value={form.lookbackCandles}
                    onChange={(value) => setForm((current) => ({ ...current, lookbackCandles: value }))}
                  />
                  <LaunchField
                    label="Signal Scale"
                    type="number"
                    step="0.1"
                    value={form.signalScale}
                    onChange={(value) => setForm((current) => ({ ...current, signalScale: value }))}
                  />
                  <LaunchField
                    label="Max Abs Position"
                    type="number"
                    step="0.05"
                    value={form.maxAbsPosition}
                    onChange={(value) => setForm((current) => ({ ...current, maxAbsPosition: value }))}
                  />
                  <LaunchField
                    label="Max Gross Position"
                    type="number"
                    step="0.05"
                    value={form.maxGrossPosition}
                    onChange={(value) => setForm((current) => ({ ...current, maxGrossPosition: value }))}
                  />
                  <LaunchField
                    label="Max Leverage"
                    type="number"
                    step="0.1"
                    value={form.maxLeverage}
                    onChange={(value) => setForm((current) => ({ ...current, maxLeverage: value }))}
                  />
                  <LaunchField
                    label="Slippage Bps"
                    type="number"
                    step="0.1"
                    value={form.slippageBps}
                    onChange={(value) => setForm((current) => ({ ...current, slippageBps: value }))}
                  />
                </div>

                <div className="flex flex-col gap-3 border border-[var(--border)] bg-[var(--bg-elevated)] p-4 lg:flex-row lg:items-center lg:justify-between">
                  <div className="text-sm leading-6 text-[var(--muted)]">
                    Granularity is fixed to <span className="mono text-[var(--text)]">ONE_MINUTE</span> in the
                    current backtest engine.
                  </div>
                  <button
                    type="submit"
                    disabled={pendingLaunch}
                    className="border border-[var(--border-strong)] bg-[rgba(84,191,255,0.08)] px-4 py-3 text-xs uppercase tracking-[0.24em] text-[var(--text)] transition hover:bg-[rgba(84,191,255,0.14)] disabled:cursor-not-allowed disabled:opacity-60"
                  >
                    {pendingLaunch ? "Launching…" : "Launch Backtest Suite"}
                  </button>
                </div>
              </form>
            </ShellPanel>

            <ShellPanel className="p-5">
              <ShellHeader eyebrow="Job Status" title="Backtest queue" action="POLL 2S" />
              {activeJob ? (
                <div className="space-y-4">
                  <div className="border border-[var(--border)] bg-[var(--bg-elevated)] p-4">
                    <div
                      className={`mono text-[10px] uppercase tracking-[0.24em] ${
                        jobTone(activeJob.status) === "accent"
                          ? "text-[var(--accent)]"
                          : jobTone(activeJob.status) === "warning"
                            ? "text-[var(--warning)]"
                            : jobTone(activeJob.status) === "danger"
                              ? "text-[var(--danger)]"
                              : "text-[var(--muted)]"
                      }`}
                    >
                      {activeJob.status}
                    </div>
                    <div className="mt-3 text-base font-medium text-[var(--text)]">{activeJob.job_id}</div>
                    <p className="mt-2 text-sm leading-6 text-[var(--muted)]">
                      {activeJob.phase_message ??
                        `${activeJob.request.productIds.join(", ")} · ${activeJob.request.strategyIds.join(", ")}`}
                    </p>
                  </div>
                  <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
                    <MetricChip label="Phase" value={activeJob.phase ?? "--"} tone={jobTone(activeJob.status)} />
                    <MetricChip
                      label="Progress"
                      value={
                        activeJob.total_runs
                          ? `${formatCount(activeJob.completed_runs ?? 0)} / ${formatCount(activeJob.total_runs)} · ${formatPercent(activeJob.progress_pct)}`
                          : "--"
                      }
                      tone={jobTone(activeJob.status)}
                    />
                    <MetricChip label="Elapsed" value={formatDurationSeconds(activeJob.elapsed_seconds)} />
                    <MetricChip label="ETA" value={formatDurationSeconds(activeJob.eta_seconds)} />
                    <MetricChip label="Heartbeat" value={formatTimestamp(activeJob.last_heartbeat_at)} />
                    <MetricChip label="Created" value={formatTimestamp(activeJob.created_at)} />
                    <MetricChip
                      label="Finished"
                      value={activeJob.finished_at ? formatTimestamp(activeJob.finished_at) : "running"}
                    />
                    <MetricChip label="Suite" value={activeJob.suite_id ?? "pending"} />
                    <MetricChip label="Run Count" value={formatCount(activeJob.run_ids.length)} />
                  </div>
                  {activeJob.error ? <ErrorBlock message={activeJob.error} /> : null}
                </div>
              ) : (
                <LoadingBlock title="No recent backtest job. Launch a suite to populate this queue." />
              )}
            </ShellPanel>
          </div>

          <ShellPanel className="p-5">
            <ShellHeader
              eyebrow="Datasets"
              title="Cached dataset registry"
              action={`${datasets.data?.count ?? 0} loaded`}
            />
            {datasets.isLoading ? (
              <LoadingBlock title="Loading cached datasets." />
            ) : datasets.error ? (
              <ErrorBlock message={datasets.error.message} />
            ) : datasets.data && datasets.data.items.length > 0 ? (
              <div className="space-y-3">
                {datasets.data.items.map((dataset) => {
                  const totalCandles = Object.values(dataset.candleCounts).reduce(
                    (sum, value) => sum + value,
                    0,
                  );
                  const active = dataset.datasetId === selectedDataset?.datasetId;
                  return (
                    <button
                      key={dataset.datasetId}
                      type="button"
                      onClick={() => startTransition(() => setSelectedDatasetId(dataset.datasetId))}
                      className={`w-full border px-4 py-4 text-left transition ${
                        active
                          ? "border-[var(--border-strong)] bg-[rgba(84,191,255,0.08)]"
                          : "border-[var(--border)] bg-[var(--bg-elevated)] hover:border-[var(--border-strong)]"
                      }`}
                    >
                      <div className="flex items-center justify-between gap-4">
                        <div className="text-sm font-medium text-[var(--text)]">{dataset.datasetId}</div>
                        <div className="mono text-[10px] uppercase tracking-[0.24em] text-[var(--muted)]">
                          {formatTimestamp(dataset.createdAt)}
                        </div>
                      </div>
                      <p className="mt-2 text-sm leading-6 text-[var(--muted)]">
                        {dataset.products.join(", ")} · {dataset.source} · {dataset.granularity}
                      </p>
                      <div className="mt-3 grid gap-2 md:grid-cols-2 xl:grid-cols-4">
                        <MetricChip label="Coverage" value={formatDateRange(dataset.start, dataset.end)} />
                        <MetricChip label="Fingerprint" value={dataset.fingerprint.slice(0, 12)} />
                        <MetricChip label="Candles" value={formatCount(totalCandles)} />
                        <MetricChip label="Status" value={active ? "selected" : "cached"} tone={active ? "accent" : "text"} />
                      </div>
                    </button>
                  );
                })}
              </div>
            ) : (
              <LoadingBlock title="No cached datasets yet." />
            )}
          </ShellPanel>

          <div className="grid gap-4 xl:grid-cols-[0.95fr_1.05fr]">
            <ShellPanel className="p-5">
              <ShellHeader
                eyebrow="Sleeves"
                title="Strategy sleeve runs"
                action={`${sleeves.data?.count ?? 0} loaded`}
              />
              {sleeves.isLoading ? (
                <LoadingBlock title="Loading strategy sleeves." />
              ) : sleeves.error ? (
                <ErrorBlock message={sleeves.error.message} />
              ) : sleeves.data && sleeves.data.items.length > 0 ? (
                <div className="space-y-3">
                  {sleeves.data.items.map((sleeve) => {
                    const active = sleeve.run_id === selectedSleeveRunId;
                    return (
                      <button
                        key={sleeve.run_id}
                        type="button"
                        onClick={() => startTransition(() => setSelectedSleeveRunId(sleeve.run_id))}
                        className={`w-full border px-4 py-4 text-left transition ${
                          active
                            ? "border-[var(--border-strong)] bg-[rgba(84,191,255,0.08)]"
                            : "border-[var(--border)] bg-[var(--bg-elevated)] hover:border-[var(--border-strong)]"
                        }`}
                      >
                        <div className="flex items-center justify-between gap-4">
                          <div className="text-sm font-medium text-[var(--text)]">
                            {sleeve.strategy_instance_id ?? sleeve.run_id}
                          </div>
                          <div className="mono text-[10px] uppercase tracking-[0.24em] text-[var(--muted)]">
                            {formatTimestamp(sleeve.created_at)}
                          </div>
                        </div>
                        <p className="mt-2 text-sm leading-6 text-[var(--muted)]">
                          {sleeve.strategy_id ?? "--"} · {formatDateRange(sleeve.date_range_start, sleeve.date_range_end)}
                        </p>
                        <div className="mt-3 grid gap-2 md:grid-cols-2 xl:grid-cols-4">
                          <MetricChip label="Return" value={formatSignedPercent(sleeve.total_return_pct)} tone="accent" />
                          <MetricChip label="P&L" value={formatMoney(sleeve.total_pnl_usdc)} />
                          <MetricChip label="Avg Exposure" value={formatPercent(sleeve.avg_abs_exposure_pct)} />
                          <MetricChip label="Turnover" value={formatMoney(sleeve.turnover_usdc)} />
                        </div>
                      </button>
                    );
                  })}
                </div>
              ) : (
                <LoadingBlock title="No strategy sleeves for the selected dataset yet." />
              )}
            </ShellPanel>

            <ShellPanel className="p-5">
              <ShellHeader
                eyebrow="Attribution"
                title="Selected sleeve attribution"
                action={effectiveSelectedSleeveRunId ?? "awaiting sleeve"}
              />
              {selectedSleeve.isLoading ? (
                <LoadingBlock title="Loading sleeve attribution." />
              ) : selectedSleeve.error ? (
                <ErrorBlock message={selectedSleeve.error.message} />
              ) : effectiveSelectedSleeveRunId && selectedSleeve.data ? (
                <div className="space-y-4">
                  <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
                    <MetricChip label="Return" value={formatSignedPercent(selectedSleeve.data.analysis.total_return_pct)} tone="accent" />
                    <MetricChip label="P&L" value={formatMoney(selectedSleeve.data.analysis.total_pnl_usdc)} />
                    <MetricChip label="Drawdown" value={formatPercent(selectedSleeve.data.analysis.max_drawdown_pct)} tone="warning" />
                    <MetricChip label="Exposure" value={formatPercent(selectedSleeve.data.analysis.avg_abs_exposure_pct)} />
                  </div>
                  <div className="overflow-x-auto border border-[var(--border)] bg-[var(--bg-elevated)]">
                    <table className="min-w-full text-left text-sm">
                      <thead className="border-b border-[var(--border)] text-[var(--muted)]">
                        <tr>
                          <th className="px-4 py-3 font-medium">Asset</th>
                          <th className="px-4 py-3 font-medium">Total P&amp;L</th>
                        </tr>
                      </thead>
                      <tbody>
                        {(((selectedSleeve.data.sleeve_analysis.asset_contributions as { product_id: string; total_pnl_usdc: number }[] | undefined) ?? [])).map((item) => (
                          <tr key={item.product_id} className="border-b border-[var(--border)] last:border-b-0">
                            <td className="px-4 py-3 text-[var(--text)]">{item.product_id}</td>
                            <td className="px-4 py-3 text-[var(--text)]">{formatMoney(item.total_pnl_usdc)}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              ) : (
                <LoadingBlock title="Select a sleeve to inspect attribution and daily metrics." />
              )}
            </ShellPanel>
          </div>

          <div className="grid gap-4 xl:grid-cols-[0.95fr_1.05fr]">
            <ShellPanel className="p-5">
              <ShellHeader
                eyebrow="Optimizer"
                title="Portfolio optimizer runs"
                action={`${portfolioRuns.data?.count ?? 0} loaded`}
              />
              {portfolioRuns.isLoading ? (
                <LoadingBlock title="Loading portfolio optimizer runs." />
              ) : portfolioRuns.error ? (
                <ErrorBlock message={portfolioRuns.error.message} />
              ) : portfolioRuns.data && portfolioRuns.data.items.length > 0 ? (
                <div className="space-y-3">
                  {portfolioRuns.data.items.map((run) => {
                    const active = run.run_id === effectiveSelectedPortfolioRunId;
                    return (
                      <button
                        key={run.run_id}
                        type="button"
                        onClick={() => startTransition(() => setSelectedPortfolioRunId(run.run_id))}
                        className={`w-full border px-4 py-4 text-left transition ${
                          active
                            ? "border-[var(--border-strong)] bg-[rgba(84,191,255,0.08)]"
                            : "border-[var(--border)] bg-[var(--bg-elevated)] hover:border-[var(--border-strong)]"
                        }`}
                      >
                        <div className="flex items-center justify-between gap-4">
                          <div className="text-sm font-medium text-[var(--text)]">{run.run_id}</div>
                          <div className="mono text-[10px] uppercase tracking-[0.24em] text-[var(--muted)]">
                            {formatTimestamp(run.created_at)}
                          </div>
                        </div>
                        <p className="mt-2 text-sm leading-6 text-[var(--muted)]">
                          {run.strategy_instance_ids.join(", ") || "no sleeves"} · {formatDateRange(run.date_range_start, run.date_range_end)}
                        </p>
                        <div className="mt-3 grid gap-2 md:grid-cols-2 xl:grid-cols-4">
                          <MetricChip label="Sharpe" value={formatSharpe(run.sharpe_ratio)} tone="accent" />
                          <MetricChip label="Return" value={formatSignedPercent(run.total_return_pct)} tone="accent" />
                          <MetricChip label="Turnover" value={formatMoney(run.total_turnover_usdc)} />
                          <MetricChip label="Gross Weight" value={formatPercent(run.avg_gross_weight)} />
                        </div>
                      </button>
                    );
                  })}
                </div>
              ) : (
                <LoadingBlock title="No portfolio optimizer runs for the selected dataset yet." />
              )}
            </ShellPanel>

            <ShellPanel className="p-5">
              <ShellHeader
                eyebrow="Detail"
                title="Selected optimizer run"
                action={effectiveSelectedPortfolioRunId ?? "awaiting optimizer"}
              />
              {selectedPortfolio.isLoading ? (
                <LoadingBlock title="Loading portfolio optimizer detail." />
              ) : selectedPortfolio.error ? (
                <ErrorBlock message={selectedPortfolio.error.message} />
              ) : effectiveSelectedPortfolioRunId && selectedPortfolio.data ? (
                <div className="space-y-4">
                  <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
                    <MetricChip label="Sharpe" value={formatSharpe(selectedPortfolio.data.analysis.sharpe_ratio)} tone="accent" />
                    <MetricChip label="Return" value={formatSignedPercent(selectedPortfolio.data.analysis.total_return_pct)} tone="accent" />
                    <MetricChip label="Turnover" value={formatMoney(selectedPortfolio.data.analysis.total_turnover_usdc)} />
                    <MetricChip label="Gross Weight" value={formatPercent(selectedPortfolio.data.analysis.avg_gross_weight)} />
                  </div>
                  <div className="grid gap-4 md:grid-cols-2">
                    <MetricChip
                      label="Dataset Coverage"
                      value={formatDateRange(
                        selectedPortfolio.data.analysis.date_range_start,
                        selectedPortfolio.data.analysis.date_range_end,
                      )}
                    />
                    <MetricChip
                      label="Strategy Lineup"
                      value={selectedPortfolio.data.analysis.strategy_instance_ids.join(", ") || "none"}
                    />
                  </div>
                  <div className="grid gap-4 xl:grid-cols-3">
                    <div className="border border-[var(--border)] bg-[var(--bg-elevated)] p-4">
                      <div className="mono text-[10px] uppercase tracking-[0.24em] text-[var(--muted)]">Equity Curve</div>
                      <div className="mt-4 h-48">
                        <ResponsiveContainer width="100%" height="100%">
                          <LineChart data={selectedPortfolio.data.analysis.equity_series}>
                            <CartesianGrid stroke="rgba(120,138,164,0.16)" vertical={false} />
                            <XAxis dataKey="label" hide />
                            <YAxis hide />
                            <Tooltip
                              contentStyle={{
                                backgroundColor: "#08121d",
                                border: "1px solid rgba(120,138,164,0.24)",
                                color: "#edf3ff",
                              }}
                            />
                            <Line type="monotone" dataKey="value" stroke="#8fd6ff" strokeWidth={2} dot={false} />
                          </LineChart>
                        </ResponsiveContainer>
                      </div>
                    </div>
                    <div className="border border-[var(--border)] bg-[var(--bg-elevated)] p-4">
                      <div className="mono text-[10px] uppercase tracking-[0.24em] text-[var(--muted)]">Drawdown</div>
                      <div className="mt-4 h-48">
                        <ResponsiveContainer width="100%" height="100%">
                          <LineChart data={selectedPortfolio.data.analysis.drawdown_series}>
                            <CartesianGrid stroke="rgba(120,138,164,0.16)" vertical={false} />
                            <XAxis dataKey="label" hide />
                            <YAxis hide />
                            <Tooltip
                              contentStyle={{
                                backgroundColor: "#08121d",
                                border: "1px solid rgba(120,138,164,0.24)",
                                color: "#edf3ff",
                              }}
                            />
                            <Line type="monotone" dataKey="value" stroke="#f1bb67" strokeWidth={2} dot={false} />
                          </LineChart>
                        </ResponsiveContainer>
                      </div>
                    </div>
                    <div className="border border-[var(--border)] bg-[var(--bg-elevated)] p-4">
                      <div className="mono text-[10px] uppercase tracking-[0.24em] text-[var(--muted)]">Gross Weight</div>
                      <div className="mt-4 h-48">
                        <ResponsiveContainer width="100%" height="100%">
                          <LineChart data={selectedPortfolio.data.analysis.gross_weight_series}>
                            <CartesianGrid stroke="rgba(120,138,164,0.16)" vertical={false} />
                            <XAxis dataKey="label" hide />
                            <YAxis hide />
                            <Tooltip
                              contentStyle={{
                                backgroundColor: "#08121d",
                                border: "1px solid rgba(120,138,164,0.24)",
                                color: "#edf3ff",
                              }}
                            />
                            <Line type="monotone" dataKey="value" stroke="#7ce3c1" strokeWidth={2} dot={false} />
                          </LineChart>
                        </ResponsiveContainer>
                      </div>
                    </div>
                  </div>
                  <div className="grid gap-4 xl:grid-cols-[1.05fr_0.95fr]">
                    <div className="overflow-x-auto border border-[var(--border)] bg-[var(--bg-elevated)]">
                      <table className="min-w-full text-left text-sm">
                        <thead className="border-b border-[var(--border)] text-[var(--muted)]">
                          <tr>
                            <th className="px-4 py-3 font-medium">Date</th>
                            <th className="px-4 py-3 font-medium">Cash</th>
                            <th className="px-4 py-3 font-medium">Gross</th>
                            <th className="px-4 py-3 font-medium">Turnover</th>
                            <th className="px-4 py-3 font-medium">Weights</th>
                          </tr>
                        </thead>
                        <tbody>
                          {selectedPortfolio.data.weights.slice(0, 8).map((snapshot) => (
                            <tr key={snapshot.date} className="border-b border-[var(--border)] last:border-b-0">
                              <td className="px-4 py-3 text-[var(--text)]">{snapshot.date}</td>
                              <td className="px-4 py-3 text-[var(--text)]">{formatPercent(snapshot.cash_weight)}</td>
                              <td className="px-4 py-3 text-[var(--text)]">{formatPercent(snapshot.gross_weight)}</td>
                              <td className="px-4 py-3 text-[var(--muted)]">{formatPercent(snapshot.turnover)}</td>
                              <td className="px-4 py-3 text-[var(--muted)]">
                                {Object.entries(snapshot.weights)
                                  .map(([instanceId, weight]) => `${instanceId} ${formatPercent(weight)}`)
                                  .join(" · ")}
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                    <div className="overflow-x-auto border border-[var(--border)] bg-[var(--bg-elevated)]">
                      <table className="min-w-full text-left text-sm">
                        <thead className="border-b border-[var(--border)] text-[var(--muted)]">
                          <tr>
                            <th className="px-4 py-3 font-medium">Strategy Sleeve</th>
                            <th className="px-4 py-3 font-medium">Strategy</th>
                            <th className="px-4 py-3 font-medium">Gross P&amp;L</th>
                          </tr>
                        </thead>
                        <tbody>
                          {selectedPortfolio.data.contributions.items.map((item) => (
                            <tr key={item.strategy_instance_id} className="border-b border-[var(--border)] last:border-b-0">
                              <td className="px-4 py-3 text-[var(--text)]">{item.strategy_instance_id}</td>
                              <td className="px-4 py-3 text-[var(--muted)]">{item.strategy_id}</td>
                              <td className="px-4 py-3 text-[var(--text)]">{formatMoney(item.total_gross_pnl_usdc)}</td>
                            </tr>
                          ))}
                          <tr className="border-t border-[var(--border)]">
                            <td className="px-4 py-3 text-[var(--muted)]" colSpan={2}>
                              Transaction Costs
                            </td>
                            <td className="px-4 py-3 text-[var(--warning)]">
                              {formatMoney(-selectedPortfolio.data.contributions.transaction_cost_total_usdc)}
                            </td>
                          </tr>
                        </tbody>
                      </table>
                    </div>
                  </div>
                </div>
              ) : (
                <LoadingBlock title="Select an optimizer run to inspect weights and performance." />
              )}
            </ShellPanel>
          </div>

          <div className="grid gap-4 xl:grid-cols-[0.92fr_1.08fr]">
            <ShellPanel className="p-5">
              <ShellHeader
                eyebrow="Suites"
                title="Completed suite manifests"
                action={`${suites.data?.count ?? 0} loaded`}
              />
              {suites.isLoading ? (
                <LoadingBlock title="Loading completed backtest suites." />
              ) : suites.data && suites.data.items.length > 0 ? (
                <div className="space-y-3">
                  {suites.data.items.map((suite) => (
                    <button
                      key={suite.suite_id}
                      type="button"
                      onClick={() => startTransition(() => setSelectedSuiteId(suite.suite_id))}
                      className={`w-full border px-4 py-4 text-left transition ${
                        suite.suite_id === selectedSuiteId
                          ? "border-[var(--border-strong)] bg-[rgba(84,191,255,0.08)]"
                          : "border-[var(--border)] bg-[var(--bg-elevated)] hover:border-[var(--border-strong)]"
                      }`}
                    >
                      <div className="flex items-center justify-between gap-4">
                        <div className="text-sm font-medium text-[var(--text)]">{suite.suite_id}</div>
                        <div className="mono text-[10px] uppercase tracking-[0.24em] text-[var(--muted)]">
                          {formatTimestamp(suite.created_at)}
                        </div>
                      </div>
                      <p className="mt-2 text-sm leading-6 text-[var(--muted)]">
                        {suite.strategies.join(", ")} · {suite.products.join(", ")}
                      </p>
                      <div className="mt-3 grid gap-2 md:grid-cols-2">
                        <MetricChip
                          label="Date Range"
                          value={formatDateRange(suite.date_range_start, suite.date_range_end)}
                        />
                        <MetricChip label="Sharpe" value={formatSharpe(suite.sharpe_ratio)} />
                      </div>
                    </button>
                  ))}
                </div>
              ) : (
                <LoadingBlock title="No completed backtest suites yet." />
              )}
            </ShellPanel>

            <ShellPanel className="p-5">
              <ShellHeader
                eyebrow="Comparison"
                title="Selected suite, sleeve, and optimizer rankings"
                action={selectedSuite.data?.ranking_policy ?? sleeveComparison.data?.ranking_policy ?? portfolioComparison.data?.ranking_policy ?? "awaiting rankings"}
              />
              {selectedSuite.isLoading && !selectedSuite.data && sleeveComparison.isLoading && !sleeveComparison.data && portfolioComparison.isLoading && !portfolioComparison.data ? (
                <LoadingBlock title="Loading suite, sleeve, and optimizer rankings." />
              ) : selectedSuite.data || sleeveComparison.data || portfolioComparison.data || selectedSuite.error || sleeveComparison.error || portfolioComparison.error ? (
                <div className="space-y-4">
                  <div className="space-y-2">
                    <div className="mono text-[10px] uppercase tracking-[0.24em] text-[var(--muted)]">Suite ranking</div>
                    {selectedSuite.error ? (
                      <ErrorBlock message={selectedSuite.error.message} />
                    ) : selectedSuite.isLoading && !selectedSuite.data ? (
                      <LoadingBlock title="Loading suite rankings." />
                    ) : selectedSuite.data ? (
                      <div className="overflow-x-auto border border-[var(--border)] bg-[var(--bg-elevated)]">
                        <table className="min-w-full text-left text-sm">
                          <thead className="border-b border-[var(--border)] text-[var(--muted)]">
                            <tr>
                              <th className="px-4 py-3 font-medium">Rank</th>
                              <th className="px-4 py-3 font-medium">Strategy</th>
                              <th className="px-4 py-3 font-medium">Date Range</th>
                              <th className="px-4 py-3 font-medium">Sharpe</th>
                              <th className="px-4 py-3 font-medium">Return</th>
                              <th className="px-4 py-3 font-medium">P&amp;L</th>
                              <th className="px-4 py-3 font-medium">Drawdown</th>
                              <th className="px-4 py-3 font-medium">Turns</th>
                            </tr>
                          </thead>
                          <tbody>
                            {selectedSuite.data.items.map((item) => (
                              <tr key={item.run_id} className="border-b border-[var(--border)] last:border-b-0">
                                <td className="px-4 py-3 text-[var(--text)]">{item.rank}</td>
                                <td className="px-4 py-3 text-[var(--text)]">
                                  <Link href={`/backtests/${item.run_id}`} className="underline decoration-[var(--border)] underline-offset-4">
                                    {item.strategy_id ?? item.run_id}
                                  </Link>
                                </td>
                                <td className="px-4 py-3 text-[var(--muted)]">{formatDateRange(item.date_range_start, item.date_range_end)}</td>
                                <td className="px-4 py-3 text-[var(--text)]">{formatSharpe(item.sharpe_ratio)}</td>
                                <td className="px-4 py-3 text-[var(--accent)]">{formatSignedPercent(item.total_return_pct)}</td>
                                <td className="px-4 py-3 text-[var(--text)]">{formatMoney(item.total_pnl_usdc)}</td>
                                <td className="px-4 py-3 text-[var(--warning)]">{formatPercent(item.max_drawdown_pct)}</td>
                                <td className="px-4 py-3 text-[var(--muted)]">{formatCount(item.fill_count)}</td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    ) : (
                      <LoadingBlock title="Select a suite to inspect ranking candidates." />
                    )}
                  </div>
                  <div className="space-y-2">
                    <div className="mono text-[10px] uppercase tracking-[0.24em] text-[var(--muted)]">Sleeve ranking</div>
                    {sleeveComparison.error ? (
                      <ErrorBlock message={sleeveComparison.error.message} />
                    ) : sleeveComparison.isLoading && !sleeveComparison.data ? (
                      <LoadingBlock title="Loading sleeve rankings." />
                    ) : sleeveComparison.data && sleeveComparison.data.items.length > 0 ? (
                      <div className="overflow-x-auto border border-[var(--border)] bg-[var(--bg-elevated)]">
                        <table className="min-w-full text-left text-sm">
                          <thead className="border-b border-[var(--border)] text-[var(--muted)]">
                            <tr>
                              <th className="px-4 py-3 font-medium">Sleeve Rank</th>
                              <th className="px-4 py-3 font-medium">Instance</th>
                              <th className="px-4 py-3 font-medium">Return</th>
                              <th className="px-4 py-3 font-medium">P&amp;L</th>
                              <th className="px-4 py-3 font-medium">Drawdown</th>
                              <th className="px-4 py-3 font-medium">Exposure</th>
                              <th className="px-4 py-3 font-medium">Turnover</th>
                            </tr>
                          </thead>
                          <tbody>
                            {sleeveComparison.data.items.map((item) => (
                              <tr key={item.run_id} className="border-b border-[var(--border)] last:border-b-0">
                                <td className="px-4 py-3 text-[var(--text)]">{item.rank}</td>
                                <td className="px-4 py-3 text-[var(--text)]">{item.strategy_instance_id ?? item.run_id}</td>
                                <td className="px-4 py-3 text-[var(--accent)]">{formatSignedPercent(item.total_return_pct)}</td>
                                <td className="px-4 py-3 text-[var(--text)]">{formatMoney(item.total_pnl_usdc)}</td>
                                <td className="px-4 py-3 text-[var(--warning)]">{formatPercent(item.max_drawdown_pct)}</td>
                                <td className="px-4 py-3 text-[var(--text)]">{formatPercent(item.avg_abs_exposure_pct)}</td>
                                <td className="px-4 py-3 text-[var(--muted)]">{formatMoney(item.turnover_usdc)}</td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    ) : (
                      <LoadingBlock title="No strategy sleeve rankings for the selected dataset yet." />
                    )}
                  </div>
                  <div className="space-y-2">
                    <div className="mono text-[10px] uppercase tracking-[0.24em] text-[var(--muted)]">Optimizer ranking</div>
                    {portfolioComparison.error ? (
                      <ErrorBlock message={portfolioComparison.error.message} />
                    ) : portfolioComparison.isLoading && !portfolioComparison.data ? (
                      <LoadingBlock title="Loading optimizer rankings." />
                    ) : portfolioComparison.data && portfolioComparison.data.items.length > 0 ? (
                      <div className="overflow-x-auto border border-[var(--border)] bg-[var(--bg-elevated)]">
                        <table className="min-w-full text-left text-sm">
                          <thead className="border-b border-[var(--border)] text-[var(--muted)]">
                            <tr>
                              <th className="px-4 py-3 font-medium">Rank</th>
                              <th className="px-4 py-3 font-medium">Run</th>
                              <th className="px-4 py-3 font-medium">Sharpe</th>
                              <th className="px-4 py-3 font-medium">Return</th>
                              <th className="px-4 py-3 font-medium">P&amp;L</th>
                              <th className="px-4 py-3 font-medium">Turnover</th>
                              <th className="px-4 py-3 font-medium">Lineup</th>
                            </tr>
                          </thead>
                          <tbody>
                            {portfolioComparison.data.items.map((item) => (
                              <tr key={item.run_id} className="border-b border-[var(--border)] last:border-b-0">
                                <td className="px-4 py-3 text-[var(--text)]">{item.rank}</td>
                                <td className="px-4 py-3 text-[var(--text)]">{item.run_id}</td>
                                <td className="px-4 py-3 text-[var(--text)]">{formatSharpe(item.sharpe_ratio)}</td>
                                <td className="px-4 py-3 text-[var(--accent)]">{formatSignedPercent(item.total_return_pct)}</td>
                                <td className="px-4 py-3 text-[var(--text)]">{formatMoney(item.total_pnl_usdc)}</td>
                                <td className="px-4 py-3 text-[var(--muted)]">{formatMoney(item.total_turnover_usdc)}</td>
                                <td className="px-4 py-3 text-[var(--muted)]">{item.strategy_instance_ids.join(", ")}</td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    ) : (
                      <LoadingBlock title="No optimizer rankings for the selected dataset yet." />
                    )}
                  </div>
                </div>
              ) : (
                <LoadingBlock title="Select a dataset to inspect suite, sleeve, and optimizer rankings." />
              )}
            </ShellPanel>
          </div>

          <ShellPanel className="p-5">
            <ShellHeader
              eyebrow="Runs"
              title="Completed backtest runs"
              action={`${backtests.data?.count ?? 0} loaded`}
            />
            {backtests.isLoading ? (
              <LoadingBlock title="Loading completed backtest runs." />
            ) : backtests.data && backtests.data.items.length > 0 ? (
              <div className="overflow-x-auto border border-[var(--border)] bg-[var(--bg-elevated)]">
                <table className="min-w-full text-left text-sm">
                  <thead className="border-b border-[var(--border)] text-[var(--muted)]">
                    <tr>
                      <th className="px-4 py-3 font-medium">Run</th>
                      <th className="px-4 py-3 font-medium">Suite</th>
                      <th className="px-4 py-3 font-medium">Strategy</th>
                      <th className="px-4 py-3 font-medium">Date Range</th>
                      <th className="px-4 py-3 font-medium">Sharpe</th>
                      <th className="px-4 py-3 font-medium">Return</th>
                      <th className="px-4 py-3 font-medium">P&amp;L</th>
                      <th className="px-4 py-3 font-medium">Drawdown</th>
                      <th className="px-4 py-3 font-medium">Fills</th>
                    </tr>
                  </thead>
                  <tbody>
                    {backtests.data.items.map((run) => (
                      <tr key={run.run_id} className="border-b border-[var(--border)] last:border-b-0">
                        <td className="px-4 py-3 text-[var(--text)]">
                          <Link
                            href={`/backtests/${run.run_id}`}
                            className="underline decoration-[var(--border)] underline-offset-4"
                          >
                            {run.run_id}
                          </Link>
                        </td>
                        <td className="px-4 py-3 text-[var(--muted)]">{run.suite_id ?? "--"}</td>
                        <td className="px-4 py-3 text-[var(--text)]">{run.strategy_id ?? "--"}</td>
                        <td className="px-4 py-3 text-[var(--muted)]">
                          {formatDateRange(run.date_range_start, run.date_range_end)}
                        </td>
                        <td className="px-4 py-3 text-[var(--text)]">{formatSharpe(run.sharpe_ratio)}</td>
                        <td className="px-4 py-3 text-[var(--accent)]">{formatSignedPercent(run.total_return_pct)}</td>
                        <td className="px-4 py-3 text-[var(--text)]">{formatMoney(run.total_pnl_usdc)}</td>
                        <td className="px-4 py-3 text-[var(--warning)]">{formatPercent(run.max_drawdown_pct)}</td>
                        <td className="px-4 py-3 text-[var(--muted)]">{formatCount(run.fill_count)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : (
              <LoadingBlock title="No completed backtest runs yet." />
            )}
          </ShellPanel>
        </section>
      </div>
    </main>
  );
}
