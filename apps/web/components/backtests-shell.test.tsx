import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { SWRConfig } from "swr";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { BacktestRunShell } from "@/components/backtest-run-shell";
import { BacktestsShell } from "@/components/backtests-shell";
import { ApiError } from "@/lib/perpfut-api";


vi.mock("next/link", () => ({
  default: ({ href, children }: { href: string; children: React.ReactNode }) => <a href={href}>{children}</a>,
}));

vi.mock("recharts", () => ({
  ResponsiveContainer: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
  LineChart: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
  CartesianGrid: () => null,
  Line: () => null,
  Tooltip: () => null,
  XAxis: () => null,
  YAxis: () => null,
}));

vi.mock("@/lib/perpfut-api", async () => {
  const actual = await vi.importActual<typeof import("@/lib/perpfut-api")>("@/lib/perpfut-api");
  return {
    ...actual,
    fetchJson: vi.fn(),
    launchSleeves: vi.fn(),
    startPortfolioRun: vi.fn(),
    startBacktest: vi.fn(),
  };
});

const { fetchJson, launchSleeves, startPortfolioRun, startBacktest } = await import("@/lib/perpfut-api");

const mockedFetchJson = vi.mocked(fetchJson);
const mockedLaunchSleeves = vi.mocked(launchSleeves);
const mockedStartPortfolioRun = vi.mocked(startPortfolioRun);
const mockedStartBacktest = vi.mocked(startBacktest);

function renderBacktestsShell() {
  return render(
    <SWRConfig value={{ provider: () => new Map(), dedupingInterval: 0 }}>
      <BacktestsShell />
    </SWRConfig>
  );
}

function renderBacktestRunShell(runId: string) {
  return render(
    <SWRConfig value={{ provider: () => new Map(), dedupingInterval: 0 }}>
      <BacktestRunShell runId={runId} />
    </SWRConfig>
  );
}

const defaultSleeveListResponse = {
  items: [
    {
      run_id: "sleeve-run-1",
      created_at: "2026-03-22T05:30:00Z",
      dataset_id: "dataset-1",
      strategy_instance_id: "mom-fast",
      strategy_id: "momentum",
      date_range_start: "2026-03-20T12:00:00+00:00",
      date_range_end: "2026-03-21T12:00:00+00:00",
      total_pnl_usdc: 140,
      total_return_pct: 0.014,
      max_drawdown_usdc: 35,
      max_drawdown_pct: 0.0035,
      avg_abs_exposure_pct: 0.21,
      turnover_usdc: 2800,
    },
  ],
  count: 1,
};

const defaultStrategyCatalogResponse = {
  items: [
    {
      strategyId: "momentum",
      label: "Momentum",
      strategyParams: [
        { key: "lookback_candles", label: "Lookback Candles", inputKind: "integer", required: true, defaultValue: 20, minValue: 1, maxValue: null, step: 1 },
        { key: "signal_scale", label: "Signal Scale", inputKind: "number", required: true, defaultValue: 35, minValue: 0, maxValue: null, step: 0.1 },
      ],
      riskOverrides: [
        { key: "max_abs_position", label: "Max Abs Position", inputKind: "number", required: false, defaultValue: 0.5, minValue: 0, maxValue: null, step: 0.01 },
        { key: "max_gross_position", label: "Max Gross Position", inputKind: "number", required: false, defaultValue: 1.0, minValue: 0, maxValue: null, step: 0.01 },
        { key: "rebalance_threshold", label: "Rebalance Threshold", inputKind: "number", required: false, defaultValue: 0.1, minValue: 0, maxValue: null, step: 0.01 },
        { key: "min_trade_notional_usdc", label: "Min Trade Notional (USDC)", inputKind: "number", required: false, defaultValue: 10, minValue: 0, maxValue: null, step: 1 },
        { key: "max_daily_drawdown_usdc", label: "Max Daily Drawdown (USDC)", inputKind: "number", required: false, defaultValue: 250, minValue: 0, maxValue: null, step: 1 },
      ],
    },
    {
      strategyId: "mean_reversion",
      label: "Mean Reversion",
      strategyParams: [
        { key: "lookback_candles", label: "Lookback Candles", inputKind: "integer", required: true, defaultValue: 20, minValue: 1, maxValue: null, step: 1 },
        { key: "signal_scale", label: "Signal Scale", inputKind: "number", required: true, defaultValue: 35, minValue: 0, maxValue: null, step: 0.1 },
      ],
      riskOverrides: [
        { key: "max_abs_position", label: "Max Abs Position", inputKind: "number", required: false, defaultValue: 0.5, minValue: 0, maxValue: null, step: 0.01 },
        { key: "max_gross_position", label: "Max Gross Position", inputKind: "number", required: false, defaultValue: 1.0, minValue: 0, maxValue: null, step: 0.01 },
        { key: "rebalance_threshold", label: "Rebalance Threshold", inputKind: "number", required: false, defaultValue: 0.1, minValue: 0, maxValue: null, step: 0.01 },
        { key: "min_trade_notional_usdc", label: "Min Trade Notional (USDC)", inputKind: "number", required: false, defaultValue: 10, minValue: 0, maxValue: null, step: 1 },
        { key: "max_daily_drawdown_usdc", label: "Max Daily Drawdown (USDC)", inputKind: "number", required: false, defaultValue: 250, minValue: 0, maxValue: null, step: 1 },
      ],
    },
  ],
  count: 2,
};

function withStrategyCatalog(handler: (path: string) => Promise<unknown>) {
  return async (path: string) => {
    if (path === "/strategy-catalog") {
      return defaultStrategyCatalogResponse;
    }
    return handler(path);
  };
}

const defaultSleeveComparisonResponse = {
  dataset_id: "dataset-1",
  ranking_policy: "rank by total_return_pct desc",
  items: [
    {
      rank: 1,
      run_id: "sleeve-run-1",
      dataset_id: "dataset-1",
      strategy_instance_id: "mom-fast",
      strategy_id: "momentum",
      date_range_start: "2026-03-20T12:00:00+00:00",
      date_range_end: "2026-03-21T12:00:00+00:00",
      total_pnl_usdc: 140,
      total_return_pct: 0.014,
      max_drawdown_usdc: 35,
      max_drawdown_pct: 0.0035,
      avg_abs_exposure_pct: 0.21,
      turnover_usdc: 2800,
      asset_contribution_totals: {
        "BTC-PERP-INTX": 90,
        "ETH-PERP-INTX": 50,
      },
    },
  ],
};

const defaultSleeveDetailResponse = {
  run_id: "sleeve-run-1",
  manifest: {
    run_id: "sleeve-run-1",
    strategy_instance_id: "mom-fast",
    dataset_id: "dataset-1",
  },
  state: {
    run_id: "sleeve-run-1",
    ending_equity_usdc: 10140,
  },
  analysis: {
    run_id: "sleeve-run-1",
    mode: "backtest",
    product_id: "MULTI_ASSET",
    strategy_id: "momentum",
    started_at: "2026-03-22T02:00:00Z",
    ended_at: "2026-03-22T02:10:00Z",
    date_range_start: "2026-03-20T12:00:00+00:00",
    date_range_end: "2026-03-21T12:00:00+00:00",
    sharpe_ratio: 1.33,
    cycle_count: 12,
    starting_equity_usdc: 10000,
    ending_equity_usdc: 10140,
    realized_pnl_usdc: 90,
    unrealized_pnl_usdc: 50,
    total_pnl_usdc: 140,
    total_return_pct: 0.014,
    max_drawdown_usdc: 35,
    max_drawdown_pct: 0.0035,
    turnover_usdc: 2800,
    fill_count: 3,
    trade_count: 3,
    avg_abs_exposure_pct: 0.21,
    max_abs_exposure_pct: 0.28,
    decision_counts: { filled: 3 },
    equity_series: [{ label: "c1", value: 10000 }, { label: "c12", value: 10140 }],
    drawdown_series: [{ label: "c1", value: 0 }, { label: "c12", value: 35 }],
    exposure_series: [{ label: "c1", value: 0.1 }, { label: "c12", value: 0.21 }],
  },
  sleeve_analysis: {
    asset_contributions: [
      { product_id: "BTC-PERP-INTX", total_pnl_usdc: 90 },
      { product_id: "ETH-PERP-INTX", total_pnl_usdc: 50 },
    ],
  },
};

const defaultPortfolioRunsResponse = {
  items: [
    {
      run_id: "portfolio-run-1",
      created_at: "2026-03-22T05:45:00Z",
      dataset_id: "dataset-1",
      date_range_start: "2026-03-20T12:00:00+00:00",
      date_range_end: "2026-03-21T12:00:00+00:00",
      sharpe_ratio: 1.92,
      total_pnl_usdc: 220,
      total_return_pct: 0.022,
      max_drawdown_usdc: 45,
      max_drawdown_pct: 0.0045,
      total_turnover_usdc: 3100,
      avg_gross_weight: 0.58,
      max_gross_weight: 0.82,
      strategy_instance_ids: ["mom-fast", "mean-slow"],
    },
  ],
  count: 1,
};

const defaultPortfolioComparisonResponse = {
  dataset_id: "dataset-1",
  ranking_policy: "rank by sharpe_ratio desc",
  items: [
    {
      rank: 1,
      run_id: "portfolio-run-1",
      created_at: "2026-03-22T05:45:00Z",
      dataset_id: "dataset-1",
      date_range_start: "2026-03-20T12:00:00+00:00",
      date_range_end: "2026-03-21T12:00:00+00:00",
      sharpe_ratio: 1.92,
      total_pnl_usdc: 220,
      total_return_pct: 0.022,
      max_drawdown_usdc: 45,
      max_drawdown_pct: 0.0045,
      total_turnover_usdc: 3100,
      avg_gross_weight: 0.58,
      max_gross_weight: 0.82,
      strategy_instance_ids: ["mom-fast", "mean-slow"],
    },
  ],
};

const defaultPortfolioDetailResponse = {
  run_id: "portfolio-run-1",
  manifest: {
    run_id: "portfolio-run-1",
    dataset_id: "dataset-1",
  },
  config: {
    optimizer: {
      lookback_days: 60,
    },
  },
  state: {
    run_id: "portfolio-run-1",
    ending_equity_usdc: 10220,
  },
  analysis: {
    run_id: "portfolio-run-1",
    dataset_id: "dataset-1",
    dataset_fingerprint: "fp-1",
    dataset_source: "coinbase",
    dataset_version: "1",
    date_range_start: "2026-03-20T12:00:00+00:00",
    date_range_end: "2026-03-21T12:00:00+00:00",
    created_at: "2026-03-22T05:45:00Z",
    starting_capital_usdc: 10000,
    ending_equity_usdc: 10220,
    total_pnl_usdc: 220,
    total_return_pct: 0.022,
    sharpe_ratio: 1.92,
    max_drawdown_usdc: 45,
    max_drawdown_pct: 0.0045,
    total_turnover_usdc: 3100,
    transaction_cost_total_usdc: 12,
    avg_gross_weight: 0.58,
    max_gross_weight: 0.82,
    strategy_instance_ids: ["mom-fast", "mean-slow"],
    sleeve_run_ids: ["sleeve-run-1", "sleeve-run-2"],
    equity_series: [{ label: "2026-03-20", value: 10000 }, { label: "2026-03-21", value: 10220 }],
    drawdown_series: [{ label: "2026-03-20", value: 0 }, { label: "2026-03-21", value: 45 }],
    gross_return_series: [{ label: "2026-03-20", value: 0.012 }, { label: "2026-03-21", value: 0.01 }],
    net_return_series: [{ label: "2026-03-20", value: 0.011 }, { label: "2026-03-21", value: 0.009 }],
    turnover_series_usdc: [{ label: "2026-03-20", value: 1500 }, { label: "2026-03-21", value: 1600 }],
    transaction_cost_series_usdc: [{ label: "2026-03-20", value: 6 }, { label: "2026-03-21", value: 6 }],
    gross_weight_series: [{ label: "2026-03-20", value: 0.52 }, { label: "2026-03-21", value: 0.58 }],
    contribution_totals_usdc: { "mom-fast": 140, "mean-slow": 80 },
  },
  weights: [
    {
      date: "2026-03-20",
      weights: { "mom-fast": 0.35, "mean-slow": 0.17 },
      cash_weight: 0.48,
      turnover: 0.22,
      gross_weight: 0.52,
    },
  ],
  diagnostics: [
    {
      date: "2026-03-20",
      expected_returns: { "mom-fast": 0.01, "mean-slow": 0.007 },
      covariance_matrix: {
        "mom-fast": { "mom-fast": 0.002, "mean-slow": 0.001 },
        "mean-slow": { "mom-fast": 0.001, "mean-slow": 0.002 },
      },
      constraint_status: "optimized",
    },
  ],
  contributions: {
    items: [
      {
        strategy_instance_id: "mom-fast",
        strategy_id: "momentum",
        sleeve_run_id: "sleeve-run-1",
        total_gross_pnl_usdc: 140,
        daily_gross_pnl_series: [{ label: "2026-03-20", value: 140 }],
      },
      {
        strategy_instance_id: "mean-slow",
        strategy_id: "mean_reversion",
        sleeve_run_id: "sleeve-run-2",
        total_gross_pnl_usdc: 80,
        daily_gross_pnl_series: [{ label: "2026-03-20", value: 80 }],
      },
    ],
    transaction_cost_total_usdc: 12,
    transaction_cost_series_usdc: [{ label: "2026-03-20", value: 12 }],
  },
};

describe("BacktestsShell", () => {
  beforeEach(() => {
    mockedFetchJson.mockReset();
    mockedLaunchSleeves.mockReset();
    mockedStartPortfolioRun.mockReset();
    mockedStartBacktest.mockReset();
  });

  it("renders the launch console, suite ranking, and completed run table", async () => {
    mockedFetchJson.mockImplementation(async (path: string) => {
      if (path === "/datasets") {
        return {
          items: [
            {
              datasetId: "dataset-1",
              createdAt: "2026-03-22T05:00:00Z",
              fingerprint: "fingerprint-123456",
              source: "coinbase",
              version: "1",
              products: ["BTC-PERP-INTX", "ETH-PERP-INTX"],
              start: "2026-03-20T12:00:00+00:00",
              end: "2026-03-21T12:00:00+00:00",
              granularity: "ONE_MINUTE",
              candleCounts: { "BTC-PERP-INTX": 1440, "ETH-PERP-INTX": 1440 },
            },
          ],
          count: 1,
        };
      }
      if (path === "/backtests") {
        return {
          items: [
            {
              run_id: "run-2",
              created_at: "2026-03-22T06:00:00Z",
              suite_id: "suite-1",
              dataset_id: "dataset-1",
              date_range_start: "2026-03-20T12:00:00+00:00",
              date_range_end: "2026-03-21T12:00:00+00:00",
              product_id: "MULTI_ASSET",
              strategy_id: "momentum",
              sharpe_ratio: 1.87,
              total_pnl_usdc: 120,
              total_return_pct: 0.012,
              max_drawdown_usdc: 40,
              max_drawdown_pct: 0.004,
              turnover_usdc: 5000,
              fill_count: 3,
              avg_abs_exposure_pct: 0.22,
              max_abs_exposure_pct: 0.35,
            },
          ],
          count: 1,
          active_job: {
            job_id: "job-1",
            status: "running",
            phase: "running_suite",
            phase_message: "Completed strategy 1 of 2: momentum",
            pid: 4001,
            created_at: "2026-03-22T06:05:00Z",
            started_at: "2026-03-22T06:05:00Z",
            finished_at: null,
            total_runs: 2,
            completed_runs: 1,
            progress_pct: 0.5,
            elapsed_seconds: 90,
            eta_seconds: 90,
            last_heartbeat_at: "2026-03-22T06:06:00Z",
            suite_id: null,
            dataset_id: null,
            run_ids: [],
            error: null,
            log_path: "runs/backtests/control/job-1.log",
            request: {
              productIds: ["BTC-PERP-INTX", "ETH-PERP-INTX"],
              strategyIds: ["momentum", "mean_reversion"],
              start: "2026-03-21T12:00:00+00:00",
              end: "2026-03-22T12:00:00+00:00",
              granularity: "ONE_MINUTE",
              startingCollateralUsdc: 10000,
              lookbackCandles: 20,
              signalScale: 12,
              maxAbsPosition: 0.5,
              maxGrossPosition: 1.0,
              maxLeverage: 2.0,
              slippageBps: 3,
            },
          },
          latest_job: null,
        };
      }
      if (path === "/backtest-suites") {
        return {
          items: [
            {
              suite_id: "suite-1",
              created_at: "2026-03-22T06:00:00Z",
              dataset_id: "dataset-1",
              date_range_start: "2026-03-20T12:00:00+00:00",
              date_range_end: "2026-03-21T12:00:00+00:00",
              sharpe_ratio: 1.87,
              products: ["BTC-PERP-INTX", "ETH-PERP-INTX"],
              strategies: ["momentum", "mean_reversion"],
              run_ids: ["run-2", "run-1"],
            },
          ],
          count: 1,
          active_job: null,
          latest_job: null,
        };
      }
      if (path === "/backtest-suites/suite-1") {
        return {
          suite_id: "suite-1",
          created_at: "2026-03-22T06:00:00Z",
          dataset_id: "dataset-1",
          date_range_start: "2026-03-20T12:00:00+00:00",
          date_range_end: "2026-03-21T12:00:00+00:00",
          sharpe_ratio: 1.87,
          products: ["BTC-PERP-INTX", "ETH-PERP-INTX"],
          strategies: ["momentum", "mean_reversion"],
          run_ids: ["run-2", "run-1"],
          ranking_policy: "return desc",
          items: [
            {
              rank: 1,
              run_id: "run-2",
              strategy_id: "momentum",
              date_range_start: "2026-03-20T12:00:00+00:00",
              date_range_end: "2026-03-21T12:00:00+00:00",
              sharpe_ratio: 1.87,
              total_pnl_usdc: 120,
              total_return_pct: 0.012,
              max_drawdown_usdc: 40,
              max_drawdown_pct: 0.004,
              turnover_usdc: 5000,
              fill_count: 3,
              avg_abs_exposure_pct: 0.22,
              max_abs_exposure_pct: 0.35,
              decision_counts: { filled: 3 },
            },
          ],
        };
      }
      if (path === "/portfolio-runs" || path === "/portfolio-runs?datasetId=dataset-1") {
        return defaultPortfolioRunsResponse;
      }
      if (path === "/portfolio-run-comparisons" || path === "/portfolio-run-comparisons?datasetId=dataset-1") {
        return defaultPortfolioComparisonResponse;
      }
      if (path === "/portfolio-runs/portfolio-run-1") {
        return defaultPortfolioDetailResponse;
      }
      if (path === "/sleeves" || path === "/sleeves?datasetId=dataset-1") {
        return defaultSleeveListResponse;
      }
      if (path === "/sleeve-comparisons" || path === "/sleeve-comparisons?datasetId=dataset-1") {
        return defaultSleeveComparisonResponse;
      }
      if (path === "/sleeves/sleeve-run-1") {
        return defaultSleeveDetailResponse;
      }
      throw new Error(`unexpected path ${path}`);
    });
    mockedStartBacktest.mockResolvedValue({
      job_id: "job-1",
      status: "running",
      phase: "running_suite",
      phase_message: "Completed strategy 1 of 2: momentum",
      pid: 4001,
      created_at: "2026-03-22T06:05:00Z",
      started_at: "2026-03-22T06:05:00Z",
      finished_at: null,
      total_runs: 2,
      completed_runs: 1,
      progress_pct: 0.5,
      elapsed_seconds: 90,
      eta_seconds: 90,
      last_heartbeat_at: "2026-03-22T06:06:00Z",
      suite_id: null,
      dataset_id: null,
      run_ids: [],
      error: null,
      log_path: "runs/backtests/control/job-1.log",
      request: {
        productIds: ["BTC-PERP-INTX", "ETH-PERP-INTX"],
        strategyIds: ["momentum", "mean_reversion"],
        start: "2026-03-21T00:00:00+00:00",
        end: "2026-03-22T00:00:00+00:00",
        granularity: "ONE_MINUTE",
        startingCollateralUsdc: 10000,
        lookbackCandles: 20,
        signalScale: 12,
        maxAbsPosition: 0.5,
        maxGrossPosition: 1.0,
        maxLeverage: 2.0,
        slippageBps: 3,
      },
    });

    renderBacktestsShell();

    expect(await screen.findByText("Start a backtest suite")).toBeInTheDocument();
    expect(screen.getByText("Cached dataset registry")).toBeInTheDocument();
    expect(screen.getAllByText("dataset-1").length).toBeGreaterThan(0);
    expect(screen.queryByText("No cached datasets yet.")).not.toBeInTheDocument();
    expect(screen.getAllByText("selected").length).toBeGreaterThan(0);
    expect(screen.getByText("Strategy sleeve runs")).toBeInTheDocument();
    expect(screen.getByText("Portfolio optimizer runs")).toBeInTheDocument();
    expect(screen.getByText("Selected optimizer run")).toBeInTheDocument();
    expect(screen.getByText("Selected suite, sleeve, and optimizer rankings")).toBeInTheDocument();
    expect(screen.getByText("Selected sleeve attribution")).toBeInTheDocument();
    expect(screen.getByText("Completed backtest runs")).toBeInTheDocument();
    expect((await screen.findAllByText("Completed strategy 1 of 2: momentum")).length).toBeGreaterThan(0);
    expect(screen.getAllByText("1.87").length).toBeGreaterThan(0);
    expect(screen.getByRole("link", { name: "run-2" })).toHaveAttribute("href", "/backtests/run-2");
    expect(screen.getAllByText("mom-fast").length).toBeGreaterThan(0);
    expect(screen.getAllByText("BTC-PERP-INTX").length).toBeGreaterThan(0);
    expect(screen.getAllByText("portfolio-run-1").length).toBeGreaterThan(0);
    expect(screen.getAllByText("1.92").length).toBeGreaterThan(0);

    await userEvent.click(screen.getByRole("button", { name: "SOL-PERP-INTX" }));
    await userEvent.click(screen.getByRole("button", { name: "Launch Backtest Suite" }));

    await waitFor(() => expect(mockedStartBacktest).toHaveBeenCalledTimes(1));
    expect(await screen.findByText(/Backtest job job-1 started/)).toBeInTheDocument();
  });

  it("renders an API error state when the console endpoints fail", async () => {
    mockedFetchJson.mockRejectedValue(new ApiError("backtest api unavailable", 500));

    renderBacktestsShell();

    expect(await screen.findByText("Backtest API unavailable")).toBeInTheDocument();
    expect(screen.getAllByText("backtest api unavailable").length).toBeGreaterThan(0);
  });

  it("switches leaderboard data when a different suite is selected", async () => {
    mockedFetchJson.mockImplementation(async (path: string) => {
      if (path === "/datasets") {
        return {
          items: [
            {
              datasetId: "dataset-1",
              createdAt: "2026-03-22T06:00:00Z",
              fingerprint: "fingerprint-123456",
              source: "coinbase",
              version: "1",
              products: ["BTC-PERP-INTX"],
              start: "2026-03-20T12:00:00+00:00",
              end: "2026-03-21T12:00:00+00:00",
              granularity: "ONE_MINUTE",
              candleCounts: { "BTC-PERP-INTX": 1440 },
            },
          ],
          count: 1,
        };
      }
      if (path === "/backtests") {
        return { items: [], count: 0, active_job: null };
      }
      if (path === "/backtest-suites") {
        return {
          items: [
            {
              suite_id: "suite-1",
              created_at: "2026-03-22T06:00:00Z",
              dataset_id: "dataset-1",
              products: ["BTC-PERP-INTX"],
              strategies: ["momentum"],
              run_ids: ["run-1"],
            },
            {
              suite_id: "suite-2",
              created_at: "2026-03-22T07:00:00Z",
              dataset_id: "dataset-2",
              products: ["ETH-PERP-INTX"],
              strategies: ["mean_reversion"],
              run_ids: ["run-2"],
            },
          ],
          count: 2,
          active_job: null,
        };
      }
      if (path === "/backtest-suites/suite-1") {
        return {
          suite_id: "suite-1",
          created_at: "2026-03-22T06:00:00Z",
          dataset_id: "dataset-1",
          products: ["BTC-PERP-INTX"],
          strategies: ["momentum"],
          run_ids: ["run-1"],
          ranking_policy: "return desc",
          items: [
            {
              rank: 1,
              run_id: "run-1",
              strategy_id: "momentum",
              total_pnl_usdc: 120,
              total_return_pct: 0.012,
              max_drawdown_usdc: 40,
              max_drawdown_pct: 0.004,
              turnover_usdc: 5000,
              fill_count: 3,
              avg_abs_exposure_pct: 0.22,
              max_abs_exposure_pct: 0.35,
              decision_counts: { filled: 3 },
            },
          ],
        };
      }
      if (path === "/backtest-suites/suite-2") {
        return {
          suite_id: "suite-2",
          created_at: "2026-03-22T07:00:00Z",
          dataset_id: "dataset-2",
          products: ["ETH-PERP-INTX"],
          strategies: ["mean_reversion"],
          run_ids: ["run-2"],
          ranking_policy: "return desc",
          items: [
            {
              rank: 1,
              run_id: "run-2",
              strategy_id: "mean_reversion",
              total_pnl_usdc: 80,
              total_return_pct: 0.008,
              max_drawdown_usdc: 20,
              max_drawdown_pct: 0.002,
              turnover_usdc: 3200,
              fill_count: 2,
              avg_abs_exposure_pct: 0.11,
              max_abs_exposure_pct: 0.2,
              decision_counts: { filled: 2 },
            },
          ],
        };
      }
      if (path === "/portfolio-runs" || path === "/portfolio-runs?datasetId=dataset-1") {
        return defaultPortfolioRunsResponse;
      }
      if (path === "/portfolio-run-comparisons" || path === "/portfolio-run-comparisons?datasetId=dataset-1") {
        return defaultPortfolioComparisonResponse;
      }
      if (path === "/portfolio-runs/portfolio-run-1") {
        return defaultPortfolioDetailResponse;
      }
      if (path === "/sleeves" || path === "/sleeves?datasetId=dataset-1") {
        return defaultSleeveListResponse;
      }
      if (path === "/sleeve-comparisons" || path === "/sleeve-comparisons?datasetId=dataset-1") {
        return defaultSleeveComparisonResponse;
      }
      if (path === "/sleeves/sleeve-run-1") {
        return defaultSleeveDetailResponse;
      }
      throw new Error(`unexpected path ${path}`);
    });

    renderBacktestsShell();

    expect(await screen.findByRole("link", { name: "momentum" })).toHaveAttribute(
      "href",
      "/backtests/run-1"
    );
    await userEvent.click(screen.getByRole("button", { name: /suite-2/i }));

    expect(await screen.findByRole("link", { name: "mean_reversion" })).toHaveAttribute(
      "href",
      "/backtests/run-2"
    );
  });

  it("shows a validation warning when a datetime input is cleared", async () => {
    mockedFetchJson.mockImplementation(async (path: string) => {
      if (path === "/datasets") {
        return { items: [], count: 0 };
      }
      if (path === "/backtests") {
        return { items: [], count: 0, active_job: null };
      }
      if (path === "/backtest-suites") {
        return { items: [], count: 0, active_job: null };
      }
      if (path === "/portfolio-runs") {
        return { items: [], count: 0 };
      }
      if (path === "/portfolio-run-comparisons") {
        return { dataset_id: null, ranking_policy: "rank by sharpe_ratio desc", items: [] };
      }
      if (path === "/sleeves") {
        return { items: [], count: 0 };
      }
      if (path === "/sleeve-comparisons") {
        return { dataset_id: null, ranking_policy: "rank by total_return_pct desc", items: [] };
      }
      throw new Error(`unexpected path ${path}`);
    });

    renderBacktestsShell();

    expect(await screen.findByText("Start a backtest suite")).toBeInTheDocument();
    await userEvent.clear(screen.getByLabelText("Start"));
    await userEvent.click(screen.getByRole("button", { name: "Launch Backtest Suite" }));

    expect(await screen.findByText("Provide both start and end datetimes.")).toBeInTheDocument();
    expect(mockedStartBacktest).not.toHaveBeenCalled();
  });

  it("renders console loading states while list endpoints are pending", async () => {
    mockedFetchJson.mockImplementation(async (path: string) => {
      if (
        path === "/backtests" ||
        path === "/backtest-suites" ||
        path === "/datasets" ||
        path === "/portfolio-runs" ||
        path === "/portfolio-run-comparisons" ||
        path === "/sleeves" ||
        path === "/sleeve-comparisons"
      ) {
        return new Promise(() => {});
      }
      throw new Error(`unexpected path ${path}`);
    });

    renderBacktestsShell();

    expect((await screen.findAllByText("Loading cached datasets.")).length).toBeGreaterThan(0);
    expect(await screen.findByText("Loading completed backtest suites.")).toBeInTheDocument();
    expect(screen.getByText("Loading completed backtest runs.")).toBeInTheDocument();
    expect(screen.getByText("Loading portfolio optimizer runs.")).toBeInTheDocument();
    expect(screen.getByText("Select a dataset to inspect suite, sleeve, and optimizer rankings.")).toBeInTheDocument();
  });

  it("renders console empty states when there are no suites or runs", async () => {
    mockedFetchJson.mockImplementation(async (path: string) => {
      if (path === "/datasets") {
        return { items: [], count: 0 };
      }
      if (path === "/backtests") {
        return { items: [], count: 0, active_job: null };
      }
      if (path === "/backtest-suites") {
        return { items: [], count: 0, active_job: null };
      }
      if (path === "/portfolio-runs") {
        return { items: [], count: 0 };
      }
      if (path === "/portfolio-run-comparisons") {
        return { dataset_id: null, ranking_policy: "rank by sharpe_ratio desc", items: [] };
      }
      if (path === "/sleeves") {
        return { items: [], count: 0 };
      }
      if (path === "/sleeve-comparisons") {
        return { dataset_id: null, ranking_policy: "rank by total_return_pct desc", items: [] };
      }
      throw new Error(`unexpected path ${path}`);
    });

    renderBacktestsShell();

    expect((await screen.findAllByText("No cached datasets yet.")).length).toBeGreaterThan(0);
    expect(await screen.findByText("No completed backtest suites yet.")).toBeInTheDocument();
    expect(screen.getByText("No strategy sleeves for the selected dataset yet.")).toBeInTheDocument();
    expect(screen.getByText("Portfolio optimizer runs")).toBeInTheDocument();
    expect(screen.getByText("Selected suite, sleeve, and optimizer rankings")).toBeInTheDocument();
    expect(screen.getByText("No portfolio optimizer runs for the selected dataset yet.")).toBeInTheDocument();
    expect(screen.getByText("Select an optimizer run to inspect weights and performance.")).toBeInTheDocument();
    expect(screen.getByText("Select a suite to inspect ranking candidates.")).toBeInTheDocument();
    expect(screen.getByText("No strategy sleeve rankings for the selected dataset yet.")).toBeInTheDocument();
    expect(screen.getByText("No optimizer rankings for the selected dataset yet.")).toBeInTheDocument();
    expect(screen.getByText("No completed backtest runs yet.")).toBeInTheDocument();
  });

  it("renders control feedback when the launch request is rejected", async () => {
    mockedFetchJson.mockImplementation(async (path: string) => {
      if (path === "/datasets") {
        return { items: [], count: 0 };
      }
      if (path === "/backtests") {
        return { items: [], count: 0, active_job: null };
      }
      if (path === "/backtest-suites") {
        return { items: [], count: 0, active_job: null };
      }
      if (path === "/portfolio-runs") {
        return { items: [], count: 0 };
      }
      if (path === "/portfolio-run-comparisons") {
        return { dataset_id: null, ranking_policy: "rank by sharpe_ratio desc", items: [] };
      }
      if (path === "/sleeves") {
        return { items: [], count: 0 };
      }
      if (path === "/sleeve-comparisons") {
        return { dataset_id: null, ranking_policy: "rank by total_return_pct desc", items: [] };
      }
      throw new Error(`unexpected path ${path}`);
    });
    mockedStartBacktest.mockRejectedValue(new ApiError("backtest job already running", 409));

    renderBacktestsShell();

    expect(await screen.findByText("Start a backtest suite")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Launch Backtest Suite" }));

    await waitFor(() => expect(mockedStartBacktest).toHaveBeenCalledTimes(1));
    expect(await screen.findByText("backtest job already running")).toBeInTheDocument();
  });

  it("renders the latest failed job when no backtest is currently active", async () => {
    mockedFetchJson.mockImplementation(async (path: string) => {
      if (path === "/datasets") {
        return { items: [], count: 0 };
      }
      if (path === "/backtests") {
        return {
          items: [],
          count: 0,
          active_job: null,
          latest_job: {
            job_id: "job-failed",
            status: "failed",
            phase: "failed",
            phase_message: "Backtest suite failed.",
            pid: null,
            created_at: "2026-03-22T08:00:00Z",
            started_at: "2026-03-22T08:00:00Z",
            finished_at: "2026-03-22T08:03:00Z",
            total_runs: 2,
            completed_runs: 1,
            progress_pct: 0.5,
            elapsed_seconds: 180,
            eta_seconds: 0,
            last_heartbeat_at: "2026-03-22T08:02:00Z",
            suite_id: null,
            dataset_id: null,
            run_ids: [],
            error: "backtest run failed: boom",
            log_path: "runs/backtests/control/job-failed.log",
            request: {
              productIds: ["BTC-PERP-INTX"],
              strategyIds: ["momentum", "mean_reversion"],
              start: "2026-03-21T12:00:00+00:00",
              end: "2026-03-22T12:00:00+00:00",
              granularity: "ONE_MINUTE",
            },
          },
        };
      }
      if (path === "/backtest-suites") {
        return { items: [], count: 0, active_job: null, latest_job: null };
      }
      if (path === "/portfolio-runs") {
        return { items: [], count: 0 };
      }
      if (path === "/portfolio-run-comparisons") {
        return { dataset_id: null, ranking_policy: "rank by sharpe_ratio desc", items: [] };
      }
      throw new Error(`unexpected path ${path}`);
    });

    renderBacktestsShell();

    expect(await screen.findByText("FAILED · job-failed")).toBeInTheDocument();
    expect(screen.getByText("backtest run failed: boom")).toBeInTheDocument();
  });

  it("renders an isolated dataset error state when only the dataset registry fails", async () => {
    mockedFetchJson.mockImplementation(async (path: string) => {
      if (path === "/datasets") {
        throw new ApiError("dataset registry unavailable", 500);
      }
      if (path === "/backtests") {
        return { items: [], count: 0, active_job: null, latest_job: null };
      }
      if (path === "/backtest-suites") {
        return { items: [], count: 0, active_job: null, latest_job: null };
      }
      if (path === "/portfolio-runs") {
        return { items: [], count: 0 };
      }
      if (path === "/portfolio-run-comparisons") {
        return { dataset_id: null, ranking_policy: "rank by sharpe_ratio desc", items: [] };
      }
      if (path === "/sleeves") {
        return { items: [], count: 0 };
      }
      if (path === "/sleeve-comparisons") {
        return { dataset_id: null, ranking_policy: "rank by total_return_pct desc", items: [] };
      }
      throw new Error(`unexpected path ${path}`);
    });

    renderBacktestsShell();

    expect((await screen.findAllByText("dataset registry unavailable")).length).toBeGreaterThan(0);
    expect(screen.queryByText("No cached datasets yet.")).not.toBeInTheDocument();
    expect(screen.getByText("No completed backtest suites yet.")).toBeInTheDocument();
  });

  it("still allows existing-sleeve optimizer launches when strategy catalog loading fails", async () => {
    mockedFetchJson.mockImplementation(async (path: string) => {
      if (path === "/strategy-catalog") {
        throw new ApiError("catalog unavailable", 500);
      }
      if (path === "/datasets") {
        return {
          items: [
            {
              datasetId: "dataset-1",
              createdAt: "2026-03-22T05:00:00Z",
              fingerprint: "fingerprint-123456",
              source: "coinbase",
              version: "1",
              products: ["BTC-PERP-INTX", "ETH-PERP-INTX"],
              start: "2026-03-20T12:00:00+00:00",
              end: "2026-03-21T12:00:00+00:00",
              granularity: "ONE_MINUTE",
              candleCounts: { "BTC-PERP-INTX": 1440, "ETH-PERP-INTX": 1440 },
            },
          ],
          count: 1,
        };
      }
      if (path === "/backtests" || path === "/backtest-suites") {
        return { items: [], count: 0, active_job: null, latest_job: null };
      }
      if (path === "/portfolio-runs" || path === "/portfolio-runs?datasetId=dataset-1") {
        return { items: [], count: 0 };
      }
      if (path === "/portfolio-run-comparisons" || path === "/portfolio-run-comparisons?datasetId=dataset-1") {
        return { dataset_id: "dataset-1", ranking_policy: "rank by sharpe_ratio desc", items: [] };
      }
      if (path === "/sleeves" || path === "/sleeves?datasetId=dataset-1") {
        return defaultSleeveListResponse;
      }
      if (path === "/sleeve-comparisons" || path === "/sleeve-comparisons?datasetId=dataset-1") {
        return defaultSleeveComparisonResponse;
      }
      if (path === "/sleeves/sleeve-run-1") {
        return defaultSleeveDetailResponse;
      }
      throw new Error(`unexpected path ${path}`);
    });
    mockedStartPortfolioRun.mockResolvedValue({
      ...defaultPortfolioDetailResponse,
      run_id: "portfolio-run-1",
    });

    renderBacktestsShell();

    expect(await screen.findByText(/catalog unavailable/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Use Existing Sleeves" })).toBeInTheDocument();

    await userEvent.click(screen.getByRole("button", { name: "Launch Optimizer" }));

    await waitFor(() => expect(mockedStartPortfolioRun).toHaveBeenCalledTimes(1));
    expect(mockedStartPortfolioRun.mock.calls[0]?.[0]).toMatchObject({
      datasetId: "dataset-1",
      sleeveRunIds: ["sleeve-run-1"],
    });
  });

  it("clears stale sleeve attribution when the selected dataset changes", async () => {
    mockedFetchJson.mockImplementation(async (path: string) => {
      if (path === "/datasets") {
        return {
          items: [
            {
              datasetId: "dataset-1",
              createdAt: "2026-03-22T05:00:00Z",
              fingerprint: "fingerprint-123456",
              source: "coinbase",
              version: "1",
              products: ["BTC-PERP-INTX"],
              start: "2026-03-20T12:00:00+00:00",
              end: "2026-03-21T12:00:00+00:00",
              granularity: "ONE_MINUTE",
              candleCounts: { "BTC-PERP-INTX": 1440 },
            },
            {
              datasetId: "dataset-2",
              createdAt: "2026-03-22T06:00:00Z",
              fingerprint: "fingerprint-654321",
              source: "coinbase",
              version: "1",
              products: ["ETH-PERP-INTX"],
              start: "2026-03-18T12:00:00+00:00",
              end: "2026-03-19T12:00:00+00:00",
              granularity: "ONE_MINUTE",
              candleCounts: { "ETH-PERP-INTX": 1440 },
            },
          ],
          count: 2,
        };
      }
      if (path === "/backtests") {
        return { items: [], count: 0, active_job: null, latest_job: null };
      }
      if (path === "/backtest-suites") {
        return { items: [], count: 0, active_job: null, latest_job: null };
      }
      if (path === "/portfolio-runs" || path === "/portfolio-runs?datasetId=dataset-1") {
        return defaultPortfolioRunsResponse;
      }
      if (path === "/portfolio-runs?datasetId=dataset-2") {
        return { items: [], count: 0 };
      }
      if (path === "/portfolio-run-comparisons") {
        return defaultPortfolioComparisonResponse;
      }
      if (path === "/portfolio-run-comparisons?datasetId=dataset-1") {
        return defaultPortfolioComparisonResponse;
      }
      if (path === "/portfolio-run-comparisons?datasetId=dataset-2") {
        return { dataset_id: "dataset-2", ranking_policy: "rank by sharpe_ratio desc", items: [] };
      }
      if (path === "/portfolio-runs/portfolio-run-1") {
        return defaultPortfolioDetailResponse;
      }
      if (path === "/sleeves") {
        return defaultSleeveListResponse;
      }
      if (path === "/sleeves?datasetId=dataset-1") {
        return defaultSleeveListResponse;
      }
      if (path === "/sleeves?datasetId=dataset-2") {
        return { items: [], count: 0 };
      }
      if (path === "/sleeve-comparisons") {
        return defaultSleeveComparisonResponse;
      }
      if (path === "/sleeve-comparisons?datasetId=dataset-1") {
        return defaultSleeveComparisonResponse;
      }
      if (path === "/sleeve-comparisons?datasetId=dataset-2") {
        return { dataset_id: "dataset-2", ranking_policy: "rank by total_return_pct desc", items: [] };
      }
      if (path === "/sleeves/sleeve-run-1") {
        return defaultSleeveDetailResponse;
      }
      throw new Error(`unexpected path ${path}`);
    });

    renderBacktestsShell();

    expect(await screen.findByText("Selected sleeve attribution")).toBeInTheDocument();
    expect(await screen.findByText("ETH-PERP-INTX")).toBeInTheDocument();

    await userEvent.click(screen.getByRole("button", { name: /dataset-2/i }));

    const attributionPanel = screen
      .getByText("Selected sleeve attribution")
      .closest("section");
    expect(attributionPanel).not.toBeNull();
    expect(within(attributionPanel as HTMLElement).queryByRole("cell", { name: "ETH-PERP-INTX" })).not.toBeInTheDocument();

    await waitFor(() =>
      expect(screen.getByText("Select a sleeve to inspect attribution and daily metrics.")).toBeInTheDocument()
    );
    expect(within(attributionPanel as HTMLElement).queryByRole("cell", { name: "ETH-PERP-INTX" })).not.toBeInTheDocument();
  });

  it("keeps suite rankings visible when sleeve comparisons fail", async () => {
    mockedFetchJson.mockImplementation(async (path: string) => {
      if (path === "/datasets") {
        return {
          items: [
            {
              datasetId: "dataset-1",
              createdAt: "2026-03-22T05:00:00Z",
              fingerprint: "fingerprint-123456",
              source: "coinbase",
              version: "1",
              products: ["BTC-PERP-INTX"],
              start: "2026-03-20T12:00:00+00:00",
              end: "2026-03-21T12:00:00+00:00",
              granularity: "ONE_MINUTE",
              candleCounts: { "BTC-PERP-INTX": 1440 },
            },
          ],
          count: 1,
        };
      }
      if (path === "/backtests") {
        return { items: [], count: 0, active_job: null, latest_job: null };
      }
      if (path === "/backtest-suites") {
        return {
          items: [
            {
              suite_id: "suite-1",
              created_at: "2026-03-22T06:00:00Z",
              dataset_id: "dataset-1",
              products: ["BTC-PERP-INTX"],
              strategies: ["momentum"],
              run_ids: ["run-1"],
            },
          ],
          count: 1,
          active_job: null,
          latest_job: null,
        };
      }
      if (path === "/backtest-suites/suite-1") {
        return {
          suite_id: "suite-1",
          created_at: "2026-03-22T06:00:00Z",
          dataset_id: "dataset-1",
          products: ["BTC-PERP-INTX"],
          strategies: ["momentum"],
          run_ids: ["run-1"],
          ranking_policy: "return desc",
          items: [
            {
              rank: 1,
              run_id: "run-1",
              strategy_id: "momentum",
              total_pnl_usdc: 120,
              total_return_pct: 0.012,
              max_drawdown_usdc: 40,
              max_drawdown_pct: 0.004,
              turnover_usdc: 5000,
              fill_count: 3,
              avg_abs_exposure_pct: 0.22,
              max_abs_exposure_pct: 0.35,
              decision_counts: { filled: 3 },
            },
          ],
        };
      }
      if (path === "/portfolio-runs" || path === "/portfolio-runs?datasetId=dataset-1") {
        return defaultPortfolioRunsResponse;
      }
      if (path === "/portfolio-run-comparisons" || path === "/portfolio-run-comparisons?datasetId=dataset-1") {
        throw new ApiError("optimizer comparison unavailable", 500);
      }
      if (path === "/portfolio-runs/portfolio-run-1") {
        return defaultPortfolioDetailResponse;
      }
      if (path === "/sleeves" || path === "/sleeves?datasetId=dataset-1") {
        return defaultSleeveListResponse;
      }
      if (path === "/sleeve-comparisons" || path === "/sleeve-comparisons?datasetId=dataset-1") {
        throw new ApiError("sleeve comparison unavailable", 500);
      }
      if (path === "/sleeves/sleeve-run-1") {
        return defaultSleeveDetailResponse;
      }
      throw new Error(`unexpected path ${path}`);
    });

    renderBacktestsShell();

    expect(await screen.findByRole("link", { name: "momentum" })).toHaveAttribute("href", "/backtests/run-1");
    expect(await screen.findByText("sleeve comparison unavailable")).toBeInTheDocument();
    expect(await screen.findByText("optimizer comparison unavailable")).toBeInTheDocument();
  });

  it("renders an isolated optimizer list error state when portfolio runs fail", async () => {
    mockedFetchJson.mockImplementation(async (path: string) => {
      if (path === "/datasets") {
        return {
          items: [
            {
              datasetId: "dataset-1",
              createdAt: "2026-03-22T05:00:00Z",
              fingerprint: "fingerprint-123456",
              source: "coinbase",
              version: "1",
              products: ["BTC-PERP-INTX"],
              start: "2026-03-20T12:00:00+00:00",
              end: "2026-03-21T12:00:00+00:00",
              granularity: "ONE_MINUTE",
              candleCounts: { "BTC-PERP-INTX": 1440 },
            },
          ],
          count: 1,
        };
      }
      if (path === "/backtests") {
        return { items: [], count: 0, active_job: null, latest_job: null };
      }
      if (path === "/backtest-suites") {
        return { items: [], count: 0, active_job: null, latest_job: null };
      }
      if (path === "/portfolio-runs" || path === "/portfolio-runs?datasetId=dataset-1") {
        throw new ApiError("portfolio runs unavailable", 500);
      }
      if (path === "/portfolio-run-comparisons" || path === "/portfolio-run-comparisons?datasetId=dataset-1") {
        return defaultPortfolioComparisonResponse;
      }
      if (path === "/sleeves" || path === "/sleeves?datasetId=dataset-1") {
        return defaultSleeveListResponse;
      }
      if (path === "/sleeve-comparisons" || path === "/sleeve-comparisons?datasetId=dataset-1") {
        return defaultSleeveComparisonResponse;
      }
      if (path === "/sleeves/sleeve-run-1") {
        return defaultSleeveDetailResponse;
      }
      throw new Error(`unexpected path ${path}`);
    });

    renderBacktestsShell();

    await waitFor(() => expect(mockedFetchJson).toHaveBeenCalledWith("/portfolio-runs?datasetId=dataset-1"));
    expect(await screen.findByText("portfolio runs unavailable")).toBeInTheDocument();
    expect(screen.getByText("Strategy sleeve runs")).toBeInTheDocument();
    expect(screen.getByText("Selected suite, sleeve, and optimizer rankings")).toBeInTheDocument();
  });

  it("renders optimizer detail errors without hiding the optimizer run list", async () => {
    mockedFetchJson.mockImplementation(async (path: string) => {
      if (path === "/datasets") {
        return {
          items: [
            {
              datasetId: "dataset-1",
              createdAt: "2026-03-22T05:00:00Z",
              fingerprint: "fingerprint-123456",
              source: "coinbase",
              version: "1",
              products: ["BTC-PERP-INTX"],
              start: "2026-03-20T12:00:00+00:00",
              end: "2026-03-21T12:00:00+00:00",
              granularity: "ONE_MINUTE",
              candleCounts: { "BTC-PERP-INTX": 1440 },
            },
          ],
          count: 1,
        };
      }
      if (path === "/backtests") {
        return { items: [], count: 0, active_job: null, latest_job: null };
      }
      if (path === "/backtest-suites") {
        return { items: [], count: 0, active_job: null, latest_job: null };
      }
      if (path === "/portfolio-runs" || path === "/portfolio-runs?datasetId=dataset-1") {
        return defaultPortfolioRunsResponse;
      }
      if (path === "/portfolio-run-comparisons" || path === "/portfolio-run-comparisons?datasetId=dataset-1") {
        return defaultPortfolioComparisonResponse;
      }
      if (path === "/portfolio-runs/portfolio-run-1") {
        throw new ApiError("portfolio detail unavailable", 500);
      }
      if (path === "/sleeves" || path === "/sleeves?datasetId=dataset-1") {
        return defaultSleeveListResponse;
      }
      if (path === "/sleeve-comparisons" || path === "/sleeve-comparisons?datasetId=dataset-1") {
        return defaultSleeveComparisonResponse;
      }
      if (path === "/sleeves/sleeve-run-1") {
        return defaultSleeveDetailResponse;
      }
      throw new Error(`unexpected path ${path}`);
    });

    renderBacktestsShell();

    expect(await screen.findByText("portfolio detail unavailable")).toBeInTheDocument();
    expect(screen.getAllByText("portfolio-run-1").length).toBeGreaterThan(0);
  });

  it("lets users add and remove sleeve builder cards and blocks invalid launches locally", async () => {
    mockedFetchJson.mockImplementation(
      withStrategyCatalog(async (path: string) => {
        if (path === "/datasets") {
          return {
            items: [
              {
                datasetId: "dataset-1",
                createdAt: "2026-03-22T05:00:00Z",
                fingerprint: "fingerprint-123456",
                source: "coinbase",
                version: "1",
                products: ["BTC-PERP-INTX", "ETH-PERP-INTX"],
                start: "2026-03-20T12:00:00+00:00",
                end: "2026-03-21T12:00:00+00:00",
                granularity: "ONE_MINUTE",
                candleCounts: { "BTC-PERP-INTX": 1440, "ETH-PERP-INTX": 1440 },
              },
            ],
            count: 1,
          };
        }
        if (path === "/backtests" || path === "/backtest-suites") {
          return { items: [], count: 0, active_job: null, latest_job: null };
        }
        if (path === "/portfolio-runs") {
          return { items: [], count: 0 };
        }
        if (path === "/portfolio-run-comparisons") {
          return { dataset_id: null, ranking_policy: "rank by sharpe_ratio desc", items: [] };
        }
        if (path === "/sleeves" || path === "/sleeves?datasetId=dataset-1") {
          return { items: [], count: 0 };
        }
        if (path === "/sleeve-comparisons" || path === "/sleeve-comparisons?datasetId=dataset-1") {
          return { dataset_id: "dataset-1", ranking_policy: "rank by total_return_pct desc", items: [] };
        }
        throw new Error(`unexpected path ${path}`);
      }),
    );

    renderBacktestsShell();

    expect(await screen.findByText("Build and launch strategy sleeves")).toBeInTheDocument();
    expect(screen.getAllByLabelText("Strategy Instance ID")).toHaveLength(1);

    await userEvent.click(screen.getByRole("button", { name: "Add Sleeve" }));
    expect(screen.getAllByLabelText("Strategy Instance ID")).toHaveLength(2);

    await userEvent.click(screen.getAllByRole("button", { name: "Remove" })[0]);
    expect(screen.getAllByLabelText("Strategy Instance ID")).toHaveLength(1);
    const launchButton = screen.getByRole("button", { name: "Launch Sleeves" });

    expect(await screen.findByText(/Select at least one asset/)).toBeInTheDocument();
    expect(launchButton).toBeDisabled();
    expect(mockedLaunchSleeves).not.toHaveBeenCalled();
  });

  it("launches sleeves, refreshes the list, and selects the returned sleeve", async () => {
    let launched = false;
    mockedFetchJson.mockImplementation(
      withStrategyCatalog(async (path: string) => {
        if (path === "/datasets") {
          return {
            items: [
              {
                datasetId: "dataset-1",
                createdAt: "2026-03-22T05:00:00Z",
                fingerprint: "fingerprint-123456",
                source: "coinbase",
                version: "1",
                products: ["BTC-PERP-INTX", "ETH-PERP-INTX"],
                start: "2026-03-20T12:00:00+00:00",
                end: "2026-03-21T12:00:00+00:00",
                granularity: "ONE_MINUTE",
                candleCounts: { "BTC-PERP-INTX": 1440, "ETH-PERP-INTX": 1440 },
              },
            ],
            count: 1,
          };
        }
        if (path === "/backtests" || path === "/backtest-suites") {
          return { items: [], count: 0, active_job: null, latest_job: null };
        }
        if (path === "/portfolio-runs") {
          return { items: [], count: 0 };
        }
        if (path === "/portfolio-run-comparisons") {
          return { dataset_id: null, ranking_policy: "rank by sharpe_ratio desc", items: [] };
        }
        if (path === "/sleeves" || path === "/sleeves?datasetId=dataset-1") {
          return launched
            ? {
                items: [
                  {
                    run_id: "sleeve-run-new",
                    created_at: "2026-03-22T06:10:00Z",
                    dataset_id: "dataset-1",
                    strategy_instance_id: "mom-launch",
                    strategy_id: "momentum",
                    date_range_start: "2026-03-20T12:00:00+00:00",
                    date_range_end: "2026-03-21T12:00:00+00:00",
                    total_pnl_usdc: 95,
                    total_return_pct: 0.0095,
                    max_drawdown_usdc: 20,
                    max_drawdown_pct: 0.002,
                    avg_abs_exposure_pct: 0.22,
                    turnover_usdc: 2400,
                  },
                ],
                count: 1,
              }
            : { items: [], count: 0 };
        }
        if (path === "/sleeve-comparisons" || path === "/sleeve-comparisons?datasetId=dataset-1") {
          return launched
            ? {
                dataset_id: "dataset-1",
                ranking_policy: "rank by total_return_pct desc",
                items: [
                  {
                    rank: 1,
                    run_id: "sleeve-run-new",
                    dataset_id: "dataset-1",
                    strategy_instance_id: "mom-launch",
                    strategy_id: "momentum",
                    date_range_start: "2026-03-20T12:00:00+00:00",
                    date_range_end: "2026-03-21T12:00:00+00:00",
                    total_pnl_usdc: 95,
                    total_return_pct: 0.0095,
                    max_drawdown_usdc: 20,
                    max_drawdown_pct: 0.002,
                    avg_abs_exposure_pct: 0.22,
                    turnover_usdc: 2400,
                    asset_contribution_totals: { "BTC-PERP-INTX": 60, "ETH-PERP-INTX": 35 },
                  },
                ],
              }
            : { dataset_id: "dataset-1", ranking_policy: "rank by total_return_pct desc", items: [] };
        }
        if (path === "/sleeves/sleeve-run-new") {
          return {
            run_id: "sleeve-run-new",
            manifest: { run_id: "sleeve-run-new", strategy_instance_id: "mom-launch", dataset_id: "dataset-1" },
            state: { run_id: "sleeve-run-new", ending_equity_usdc: 10095 },
            analysis: {
              ...defaultSleeveDetailResponse.analysis,
              run_id: "sleeve-run-new",
              total_pnl_usdc: 95,
              total_return_pct: 0.0095,
            },
            sleeve_analysis: {
              asset_contributions: [
                { product_id: "BTC-PERP-INTX", total_pnl_usdc: 60 },
                { product_id: "ETH-PERP-INTX", total_pnl_usdc: 35 },
              ],
            },
          };
        }
        throw new Error(`unexpected path ${path}`);
      }),
    );
    mockedLaunchSleeves.mockImplementation(async (request) => {
      launched = true;
      return {
        items: [
          {
            run_id: "sleeve-run-new",
            created_at: "2026-03-22T06:10:00Z",
            dataset_id: "dataset-1",
            strategy_instance_id: "mom-launch",
            strategy_id: "momentum",
            date_range_start: "2026-03-20T12:00:00+00:00",
            date_range_end: "2026-03-21T12:00:00+00:00",
            total_pnl_usdc: 95,
            total_return_pct: 0.0095,
            max_drawdown_usdc: 20,
            max_drawdown_pct: 0.002,
            avg_abs_exposure_pct: 0.22,
            turnover_usdc: 2400,
          },
        ],
        count: 1,
      };
    });

    renderBacktestsShell();

    expect(await screen.findByText("Build and launch strategy sleeves")).toBeInTheDocument();
    const researchControls = screen
      .getByText("Build and launch strategy sleeves")
      .closest("section");
    expect(researchControls).not.toBeNull();
    await userEvent.clear(screen.getByLabelText("Strategy Instance ID"));
    await userEvent.type(screen.getByLabelText("Strategy Instance ID"), "mom-launch");
    await userEvent.click(within(researchControls!).getByRole("button", { name: "BTC-PERP-INTX" }));
    await userEvent.click(screen.getByRole("button", { name: "Launch Sleeves" }));

    await waitFor(() => expect(mockedLaunchSleeves).toHaveBeenCalledTimes(1));
    expect(mockedLaunchSleeves.mock.calls[0]?.[0]).toMatchObject({
      datasetId: "dataset-1",
      strategyInstances: [
        {
          strategyInstanceId: "mom-launch",
          strategyId: "momentum",
          universe: ["BTC-PERP-INTX"],
        },
      ],
    });
    expect(await screen.findByText("Launched 1 sleeve for dataset-1.")).toBeInTheDocument();
  });

  it("submits an optimizer launch from existing sleeves with the selected sleeve ids", async () => {
    let launched = false;
    mockedFetchJson.mockImplementation(
      withStrategyCatalog(async (path: string) => {
        if (path === "/datasets") {
          return {
            items: [
              {
                datasetId: "dataset-1",
                createdAt: "2026-03-22T05:00:00Z",
                fingerprint: "fingerprint-123456",
                source: "coinbase",
                version: "1",
                products: ["BTC-PERP-INTX", "ETH-PERP-INTX"],
                start: "2026-03-20T12:00:00+00:00",
                end: "2026-03-21T12:00:00+00:00",
                granularity: "ONE_MINUTE",
                candleCounts: { "BTC-PERP-INTX": 1440, "ETH-PERP-INTX": 1440 },
              },
            ],
            count: 1,
          };
        }
        if (path === "/backtests" || path === "/backtest-suites") {
          return { items: [], count: 0, active_job: null, latest_job: null };
        }
        if (path === "/sleeves" || path === "/sleeves?datasetId=dataset-1") {
          return defaultSleeveListResponse;
        }
        if (path === "/sleeve-comparisons" || path === "/sleeve-comparisons?datasetId=dataset-1") {
          return defaultSleeveComparisonResponse;
        }
        if (path === "/sleeves/sleeve-run-1") {
          return defaultSleeveDetailResponse;
        }
        if (path === "/portfolio-runs" || path === "/portfolio-runs?datasetId=dataset-1") {
          return launched
            ? {
                items: [
                  {
                    run_id: "portfolio-run-new",
                    created_at: "2026-03-22T06:20:00Z",
                    dataset_id: "dataset-1",
                    date_range_start: "2026-03-20T12:00:00+00:00",
                    date_range_end: "2026-03-21T12:00:00+00:00",
                    sharpe_ratio: 1.4,
                    total_pnl_usdc: 220,
                    total_return_pct: 0.022,
                    max_drawdown_usdc: 40,
                    max_drawdown_pct: 0.004,
                    total_turnover_usdc: 1800,
                    avg_gross_weight: 0.5,
                    max_gross_weight: 0.7,
                    strategy_instance_ids: ["mom-fast"],
                  },
                ],
                count: 1,
              }
            : { items: [], count: 0 };
        }
        if (path === "/portfolio-run-comparisons" || path === "/portfolio-run-comparisons?datasetId=dataset-1") {
          return launched
            ? {
                dataset_id: "dataset-1",
                ranking_policy: "rank by sharpe_ratio desc",
                items: [
                  {
                    rank: 1,
                    run_id: "portfolio-run-new",
                    created_at: "2026-03-22T06:20:00Z",
                    dataset_id: "dataset-1",
                    date_range_start: "2026-03-20T12:00:00+00:00",
                    date_range_end: "2026-03-21T12:00:00+00:00",
                    sharpe_ratio: 1.4,
                    total_pnl_usdc: 220,
                    total_return_pct: 0.022,
                    max_drawdown_usdc: 40,
                    max_drawdown_pct: 0.004,
                    total_turnover_usdc: 1800,
                    avg_gross_weight: 0.5,
                    max_gross_weight: 0.7,
                    strategy_instance_ids: ["mom-fast"],
                  },
                ],
              }
            : { dataset_id: "dataset-1", ranking_policy: "rank by sharpe_ratio desc", items: [] };
        }
        if (path === "/portfolio-runs/portfolio-run-new") {
          return {
            run_id: "portfolio-run-new",
            manifest: { run_id: "portfolio-run-new", dataset_id: "dataset-1", sleeve_run_ids: ["sleeve-run-1"] },
            config: { lookback_days: 60 },
            state: { ending_equity_usdc: 10220 },
            analysis: {
              ...defaultPortfolioDetailResponse.analysis,
              run_id: "portfolio-run-new",
              total_pnl_usdc: 220,
              total_return_pct: 0.022,
              sharpe_ratio: 1.4,
              sleeve_run_ids: ["sleeve-run-1"],
              strategy_instance_ids: ["mom-fast"],
            },
            weights: defaultPortfolioDetailResponse.weights,
            diagnostics: defaultPortfolioDetailResponse.diagnostics,
            contributions: {
              items: [
                {
                  strategy_instance_id: "mom-fast",
                  strategy_id: "momentum",
                  sleeve_run_id: "sleeve-run-1",
                  total_gross_pnl_usdc: 120,
                  daily_gross_pnl_series: [{ label: "2026-03-20", value: 120 }],
                },
              ],
              transaction_cost_total_usdc: 6,
              transaction_cost_series_usdc: [{ label: "2026-03-20", value: 6 }],
            },
          };
        }
        throw new Error(`unexpected path ${path}`);
      }),
    );
    mockedStartPortfolioRun.mockImplementation(async (request) => {
      launched = true;
      return {
        run_id: "portfolio-run-new",
        manifest: { run_id: "portfolio-run-new", dataset_id: "dataset-1", sleeve_run_ids: ["sleeve-run-1"] },
        config: { lookback_days: 60 },
        state: { ending_equity_usdc: 10220 },
        analysis: {
          ...defaultPortfolioDetailResponse.analysis,
          run_id: "portfolio-run-new",
          total_pnl_usdc: 220,
          total_return_pct: 0.022,
          sharpe_ratio: 1.4,
          sleeve_run_ids: ["sleeve-run-1"],
          strategy_instance_ids: ["mom-fast"],
        },
        weights: defaultPortfolioDetailResponse.weights,
        diagnostics: defaultPortfolioDetailResponse.diagnostics,
        contributions: {
          items: [
            {
              strategy_instance_id: "mom-fast",
              strategy_id: "momentum",
              sleeve_run_id: "sleeve-run-1",
              total_gross_pnl_usdc: 120,
              daily_gross_pnl_series: [{ label: "2026-03-20", value: 120 }],
            },
          ],
          transaction_cost_total_usdc: 6,
          transaction_cost_series_usdc: [{ label: "2026-03-20", value: 6 }],
        },
      };
    });

    renderBacktestsShell();

    expect(await screen.findByText("Build and launch strategy sleeves")).toBeInTheDocument();
    const optimizerDetail = screen.getByText("Selected optimizer run").closest("section");
    expect(optimizerDetail).not.toBeNull();
    await userEvent.click(screen.getByRole("button", { name: "Launch Optimizer" }));

    await waitFor(() => expect(mockedStartPortfolioRun).toHaveBeenCalledTimes(1));
    expect(mockedStartPortfolioRun.mock.calls[0]?.[0]).toMatchObject({
      datasetId: "dataset-1",
      sleeveRunIds: ["sleeve-run-1"],
    });
    await waitFor(() =>
      expect(mockedFetchJson).toHaveBeenCalledWith("/portfolio-runs/portfolio-run-new"),
    );
    expect(await within(optimizerDetail!).findByText("portfolio-run-new")).toBeInTheDocument();
    expect(within(optimizerDetail!).getAllByText("mom-fast").length).toBeGreaterThan(0);
    expect(mockedLaunchSleeves).not.toHaveBeenCalled();
  });

  it("submits an optimizer launch in auto-build mode with builder strategy instances", async () => {
    let launched = false;
    mockedFetchJson.mockImplementation(
      withStrategyCatalog(async (path: string) => {
        if (path === "/datasets") {
          return {
            items: [
              {
                datasetId: "dataset-1",
                createdAt: "2026-03-22T05:00:00Z",
                fingerprint: "fingerprint-123456",
                source: "coinbase",
                version: "1",
                products: ["BTC-PERP-INTX", "ETH-PERP-INTX"],
                start: "2026-03-20T12:00:00+00:00",
                end: "2026-03-21T12:00:00+00:00",
                granularity: "ONE_MINUTE",
                candleCounts: { "BTC-PERP-INTX": 1440, "ETH-PERP-INTX": 1440 },
              },
            ],
            count: 1,
          };
        }
        if (path === "/backtests" || path === "/backtest-suites") {
          return { items: [], count: 0, active_job: null, latest_job: null };
        }
        if (path === "/sleeves" || path === "/sleeves?datasetId=dataset-1") {
          return launched
            ? {
                items: [
                  {
                    run_id: "sleeve-run-auto",
                    created_at: "2026-03-22T06:30:00Z",
                    dataset_id: "dataset-1",
                    strategy_instance_id: "mom-auto",
                    strategy_id: "momentum",
                    date_range_start: "2026-03-20T12:00:00+00:00",
                    date_range_end: "2026-03-21T12:00:00+00:00",
                    total_pnl_usdc: 70,
                    total_return_pct: 0.007,
                    max_drawdown_usdc: 18,
                    max_drawdown_pct: 0.0018,
                    avg_abs_exposure_pct: 0.19,
                    turnover_usdc: 1500,
                  },
                ],
                count: 1,
              }
            : { items: [], count: 0 };
        }
        if (path === "/sleeve-comparisons" || path === "/sleeve-comparisons?datasetId=dataset-1") {
          return launched
            ? {
                dataset_id: "dataset-1",
                ranking_policy: "rank by total_return_pct desc",
                items: [
                  {
                    rank: 1,
                    run_id: "sleeve-run-auto",
                    dataset_id: "dataset-1",
                    strategy_instance_id: "mom-auto",
                    strategy_id: "momentum",
                    date_range_start: "2026-03-20T12:00:00+00:00",
                    date_range_end: "2026-03-21T12:00:00+00:00",
                    total_pnl_usdc: 70,
                    total_return_pct: 0.007,
                    max_drawdown_usdc: 18,
                    max_drawdown_pct: 0.0018,
                    avg_abs_exposure_pct: 0.19,
                    turnover_usdc: 1500,
                    asset_contribution_totals: { "BTC-PERP-INTX": 70 },
                  },
                ],
              }
            : { dataset_id: "dataset-1", ranking_policy: "rank by total_return_pct desc", items: [] };
        }
        if (path === "/sleeves/sleeve-run-auto") {
          return {
            run_id: "sleeve-run-auto",
            manifest: { run_id: "sleeve-run-auto", strategy_instance_id: "mom-auto", dataset_id: "dataset-1" },
            state: { ending_equity_usdc: 10070 },
            analysis: {
              ...defaultSleeveDetailResponse.analysis,
              run_id: "sleeve-run-auto",
              total_pnl_usdc: 70,
              total_return_pct: 0.007,
            },
            sleeve_analysis: {
              asset_contributions: [{ product_id: "BTC-PERP-INTX", total_pnl_usdc: 70 }],
            },
          };
        }
        if (path === "/portfolio-runs" || path === "/portfolio-runs?datasetId=dataset-1") {
          return launched
            ? {
                items: [
                  {
                    run_id: "portfolio-run-auto",
                    created_at: "2026-03-22T06:35:00Z",
                    dataset_id: "dataset-1",
                    date_range_start: "2026-03-20T12:00:00+00:00",
                    date_range_end: "2026-03-21T12:00:00+00:00",
                    sharpe_ratio: 0.9,
                    total_pnl_usdc: 140,
                    total_return_pct: 0.014,
                    max_drawdown_usdc: 28,
                    max_drawdown_pct: 0.0028,
                    total_turnover_usdc: 900,
                    avg_gross_weight: 0.35,
                    max_gross_weight: 0.45,
                    strategy_instance_ids: ["mom-auto"],
                  },
                ],
                count: 1,
              }
            : { items: [], count: 0 };
        }
        if (path === "/portfolio-run-comparisons" || path === "/portfolio-run-comparisons?datasetId=dataset-1") {
          return launched
            ? {
                dataset_id: "dataset-1",
                ranking_policy: "rank by sharpe_ratio desc",
                items: [
                  {
                    rank: 1,
                    run_id: "portfolio-run-auto",
                    created_at: "2026-03-22T06:35:00Z",
                    dataset_id: "dataset-1",
                    date_range_start: "2026-03-20T12:00:00+00:00",
                    date_range_end: "2026-03-21T12:00:00+00:00",
                    sharpe_ratio: 0.9,
                    total_pnl_usdc: 140,
                    total_return_pct: 0.014,
                    max_drawdown_usdc: 28,
                    max_drawdown_pct: 0.0028,
                    total_turnover_usdc: 900,
                    avg_gross_weight: 0.35,
                    max_gross_weight: 0.45,
                    strategy_instance_ids: ["mom-auto"],
                  },
                ],
              }
            : { dataset_id: "dataset-1", ranking_policy: "rank by sharpe_ratio desc", items: [] };
        }
        if (path === "/portfolio-runs/portfolio-run-auto") {
          return {
            run_id: "portfolio-run-auto",
            manifest: { run_id: "portfolio-run-auto", dataset_id: "dataset-1", sleeve_run_ids: ["sleeve-run-auto"] },
            config: { lookback_days: 60 },
            state: { ending_equity_usdc: 10140 },
            analysis: {
              ...defaultPortfolioDetailResponse.analysis,
              run_id: "portfolio-run-auto",
              total_pnl_usdc: 140,
              total_return_pct: 0.014,
              sharpe_ratio: 0.9,
              sleeve_run_ids: ["sleeve-run-auto"],
              strategy_instance_ids: ["mom-auto"],
            },
            weights: defaultPortfolioDetailResponse.weights,
            diagnostics: defaultPortfolioDetailResponse.diagnostics,
            contributions: {
              items: [
                {
                  strategy_instance_id: "mom-auto",
                  strategy_id: "momentum",
                  sleeve_run_id: "sleeve-run-auto",
                  total_gross_pnl_usdc: 88,
                  daily_gross_pnl_series: [{ label: "2026-03-20", value: 88 }],
                },
              ],
              transaction_cost_total_usdc: 4,
              transaction_cost_series_usdc: [{ label: "2026-03-20", value: 4 }],
            },
          };
        }
        throw new Error(`unexpected path ${path}`);
      }),
    );
    mockedStartPortfolioRun.mockImplementation(async (request) => {
      launched = true;
      return {
        run_id: "portfolio-run-auto",
        manifest: { run_id: "portfolio-run-auto", dataset_id: "dataset-1", sleeve_run_ids: ["sleeve-run-auto"] },
        config: { lookback_days: 60 },
        state: { ending_equity_usdc: 10140 },
        analysis: {
          ...defaultPortfolioDetailResponse.analysis,
          run_id: "portfolio-run-auto",
          total_pnl_usdc: 140,
          total_return_pct: 0.014,
          sharpe_ratio: 0.9,
          sleeve_run_ids: ["sleeve-run-auto"],
          strategy_instance_ids: ["mom-auto"],
        },
        weights: defaultPortfolioDetailResponse.weights,
        diagnostics: defaultPortfolioDetailResponse.diagnostics,
        contributions: {
          items: [
            {
              strategy_instance_id: "mom-auto",
              strategy_id: "momentum",
              sleeve_run_id: "sleeve-run-auto",
              total_gross_pnl_usdc: 88,
              daily_gross_pnl_series: [{ label: "2026-03-20", value: 88 }],
            },
          ],
          transaction_cost_total_usdc: 4,
          transaction_cost_series_usdc: [{ label: "2026-03-20", value: 4 }],
        },
      };
    });

    renderBacktestsShell();

    expect(await screen.findByText("Build and launch strategy sleeves")).toBeInTheDocument();
    const researchControls = screen.getByText("Build and launch strategy sleeves").closest("section");
    const optimizerDetail = screen.getByText("Selected optimizer run").closest("section");
    expect(researchControls).not.toBeNull();
    expect(optimizerDetail).not.toBeNull();

    await userEvent.click(screen.getByRole("button", { name: "Auto-Build From Builder" }));
    await userEvent.clear(screen.getByLabelText("Strategy Instance ID"));
    await userEvent.type(screen.getByLabelText("Strategy Instance ID"), "mom-auto");
    await userEvent.click(within(researchControls!).getByRole("button", { name: "BTC-PERP-INTX" }));
    await userEvent.click(screen.getByRole("button", { name: "Launch Optimizer" }));

    await waitFor(() => expect(mockedStartPortfolioRun).toHaveBeenCalledTimes(1));
    expect(mockedStartPortfolioRun.mock.calls[0]?.[0]).toMatchObject({
      datasetId: "dataset-1",
      strategyInstances: [
        {
          strategyInstanceId: "mom-auto",
          strategyId: "momentum",
          universe: ["BTC-PERP-INTX"],
        },
      ],
    });
    await waitFor(() =>
      expect(mockedFetchJson).toHaveBeenCalledWith("/portfolio-runs/portfolio-run-auto"),
    );
    expect(await within(optimizerDetail!).findByText("portfolio-run-auto")).toBeInTheDocument();
    expect(within(optimizerDetail!).getAllByText("mom-auto").length).toBeGreaterThan(0);
    expect(mockedLaunchSleeves).not.toHaveBeenCalled();
  });
});

describe("BacktestRunShell", () => {
  it("renders backtest analysis, decisions, fills, and per-asset positions", async () => {
    mockedFetchJson.mockImplementation(async (path: string) => {
      if (path === "/backtests/suite-run-1") {
        return {
          run_id: "suite-run-1",
          manifest: {
            run_id: "suite-run-1",
            suite_id: "suite-1",
            dataset_id: "dataset-1",
            strategy_id: "momentum",
          },
          state: {
            cycle_id: "cycle-4",
            portfolio: {
              equity_usdc: 10120,
              gross_notional_usdc: 4200,
              realized_pnl_usdc: 70,
              unrealized_pnl_usdc: 50,
            },
            asset_positions: {
              "BTC-PERP-INTX": {
                quantity: 0.12,
                entry_price: 100,
                mark_price: 103,
                realized_pnl_usdc: 40,
              },
            },
          },
          analysis: {
            run_id: "suite-run-1",
            mode: "backtest",
            product_id: "MULTI_ASSET",
            strategy_id: "momentum",
            started_at: "2026-03-22T02:00:00Z",
            ended_at: "2026-03-22T02:10:00Z",
            date_range_start: "2026-03-20T12:00:00+00:00",
            date_range_end: "2026-03-21T12:00:00+00:00",
            sharpe_ratio: 1.52,
            cycle_count: 12,
            starting_equity_usdc: 10000,
            ending_equity_usdc: 10120,
            realized_pnl_usdc: 70,
            unrealized_pnl_usdc: 50,
            total_pnl_usdc: 120,
            total_return_pct: 0.012,
            max_drawdown_usdc: 35,
            max_drawdown_pct: 0.0035,
            turnover_usdc: 4800,
            fill_count: 3,
            trade_count: 3,
            avg_abs_exposure_pct: 0.22,
            max_abs_exposure_pct: 0.35,
            decision_counts: { filled: 3 },
            equity_series: [{ label: "c1", value: 10000 }, { label: "c12", value: 10120 }],
            drawdown_series: [{ label: "c1", value: 0 }, { label: "c12", value: 35 }],
            exposure_series: [{ label: "c1", value: 0.1 }, { label: "c12", value: 0.22 }],
          },
        };
      }
      if (path === "/backtests/suite-run-1/events?limit=20") {
        return {
          run_id: "suite-run-1",
          count: 1,
          items: [
            {
              cycle_id: "cycle-4",
              execution_summary: {
                action: "filled",
                reason_code: "filled",
                summary: "Filled one asset toward target.",
              },
              asset_decisions: {
                "BTC-PERP-INTX": {
                  signal: { target_position: 0.25 },
                  risk_decision: { delta_notional_usdc: 1500 },
                  execution_summary: { action: "filled", summary: "Filled BTC rebalance." },
                },
              },
            },
          ],
        };
      }
      if (path === "/backtests/suite-run-1/fills?limit=20") {
        return {
          run_id: "suite-run-1",
          count: 1,
          items: [
            {
              cycle_id: "cycle-4",
              product_id: "BTC-PERP-INTX",
              fill: { side: "BUY", quantity: 0.02, price: 103 },
            },
          ],
        };
      }
      if (path === "/backtests/suite-run-1/positions?limit=20") {
        return {
          run_id: "suite-run-1",
          count: 1,
          items: [
            {
              cycle_id: "cycle-4",
              asset_positions: {
                "BTC-PERP-INTX": {
                  quantity: 0.12,
                  entry_price: 100,
                  mark_price: 103,
                  realized_pnl_usdc: 40,
                },
              },
            },
          ],
        };
      }
      throw new Error(`unexpected path ${path}`);
    });

    renderBacktestRunShell("suite-run-1");

    expect(await screen.findByText("Canonical backtest analysis")).toBeInTheDocument();
    expect(screen.getByText("Latest asset decision set")).toBeInTheDocument();
    expect(screen.getByText("Recent backtest fill tape")).toBeInTheDocument();
    expect(screen.getByText("Latest per-asset positions")).toBeInTheDocument();
    expect(screen.getAllByText("1.52").length).toBeGreaterThan(0);
    expect(screen.getByRole("link", { name: /Back to Backtests/i })).toHaveAttribute("href", "/backtests");
  });

  it("keeps artifact panels in loading state while secondary requests are still pending", async () => {
    mockedFetchJson.mockImplementation(async (path: string) => {
      if (path === "/backtests/suite-run-2") {
        return {
          run_id: "suite-run-2",
          manifest: {
            run_id: "suite-run-2",
            suite_id: "suite-2",
            dataset_id: "dataset-2",
            strategy_id: "momentum",
          },
          state: {
            cycle_id: "cycle-2",
            portfolio: {
              equity_usdc: 10020,
              gross_notional_usdc: 1200,
              realized_pnl_usdc: 15,
              unrealized_pnl_usdc: 5,
            },
          },
          analysis: {
            run_id: "suite-run-2",
            mode: "backtest",
            product_id: "MULTI_ASSET",
            strategy_id: "momentum",
            started_at: "2026-03-22T03:00:00Z",
            ended_at: "2026-03-22T03:05:00Z",
            cycle_count: 6,
            starting_equity_usdc: 10000,
            ending_equity_usdc: 10020,
            realized_pnl_usdc: 15,
            unrealized_pnl_usdc: 5,
            total_pnl_usdc: 20,
            total_return_pct: 0.002,
            max_drawdown_usdc: 10,
            max_drawdown_pct: 0.001,
            turnover_usdc: 900,
            fill_count: 1,
            trade_count: 1,
            avg_abs_exposure_pct: 0.08,
            max_abs_exposure_pct: 0.12,
            decision_counts: { filled: 1 },
            equity_series: [{ label: "c1", value: 10000 }, { label: "c6", value: 10020 }],
            drawdown_series: [{ label: "c1", value: 0 }, { label: "c6", value: 10 }],
            exposure_series: [{ label: "c1", value: 0 }, { label: "c6", value: 0.08 }],
          },
        };
      }
      if (
        path === "/backtests/suite-run-2/events?limit=20" ||
        path === "/backtests/suite-run-2/fills?limit=20" ||
        path === "/backtests/suite-run-2/positions?limit=20"
      ) {
        return new Promise(() => {});
      }
      throw new Error(`unexpected path ${path}`);
    });

    renderBacktestRunShell("suite-run-2");

    expect(await screen.findByText("Canonical backtest analysis")).toBeInTheDocument();
    expect(screen.getByText("Loading the latest asset decision set.")).toBeInTheDocument();
    expect(screen.getByText("Loading recent backtest fills.")).toBeInTheDocument();
    expect(screen.getByText("Loading the backtest event stream.")).toBeInTheDocument();
    expect(screen.queryByText("This backtest run has no recorded fills yet.")).not.toBeInTheDocument();
    expect(screen.queryByText("No event stream is available for this backtest run.")).not.toBeInTheDocument();
  });

  it("renders the top-level loading state before the detail payload arrives", async () => {
    mockedFetchJson.mockImplementation(async (path: string) => {
      if (path === "/backtests/suite-run-loading") {
        return new Promise(() => {});
      }
      throw new Error(`unexpected path ${path}`);
    });

    renderBacktestRunShell("suite-run-loading");

    expect(await screen.findByText("Loading backtest artifacts")).toBeInTheDocument();
    expect(screen.getByText("Polling the local backtest API for detail, events, fills, and positions.")).toBeInTheDocument();
  });

  it("renders the detail error state when the API request fails", async () => {
    mockedFetchJson.mockRejectedValue(new ApiError("backtest detail unavailable", 500));

    renderBacktestRunShell("suite-run-error");

    expect(await screen.findByText("Unable to load backtest artifacts")).toBeInTheDocument();
    expect(screen.getByText("backtest detail unavailable")).toBeInTheDocument();
  });

  it("renders the detail error state when a secondary artifact request fails", async () => {
    mockedFetchJson.mockImplementation(async (path: string) => {
      if (path === "/backtests/suite-run-partial-error") {
        return {
          run_id: "suite-run-partial-error",
          manifest: {
            run_id: "suite-run-partial-error",
            suite_id: "suite-err",
            dataset_id: "dataset-err",
            strategy_id: "momentum",
          },
          state: {
            cycle_id: "cycle-3",
            portfolio: {
              equity_usdc: 10010,
              gross_notional_usdc: 1000,
              realized_pnl_usdc: 5,
              unrealized_pnl_usdc: 5,
            },
          },
          analysis: {
            run_id: "suite-run-partial-error",
            mode: "backtest",
            product_id: "MULTI_ASSET",
            strategy_id: "momentum",
            started_at: "2026-03-22T04:10:00Z",
            ended_at: "2026-03-22T04:15:00Z",
            cycle_count: 5,
            starting_equity_usdc: 10000,
            ending_equity_usdc: 10010,
            realized_pnl_usdc: 5,
            unrealized_pnl_usdc: 5,
            total_pnl_usdc: 10,
            total_return_pct: 0.001,
            max_drawdown_usdc: 4,
            max_drawdown_pct: 0.0004,
            turnover_usdc: 500,
            fill_count: 1,
            trade_count: 1,
            avg_abs_exposure_pct: 0.05,
            max_abs_exposure_pct: 0.08,
            decision_counts: { filled: 1 },
            equity_series: [{ label: "c1", value: 10000 }, { label: "c5", value: 10010 }],
            drawdown_series: [{ label: "c1", value: 0 }, { label: "c5", value: 4 }],
            exposure_series: [{ label: "c1", value: 0 }, { label: "c5", value: 0.05 }],
          },
        };
      }
      if (path === "/backtests/suite-run-partial-error/events?limit=20") {
        throw new ApiError("event stream unavailable", 500);
      }
      if (
        path === "/backtests/suite-run-partial-error/fills?limit=20" ||
        path === "/backtests/suite-run-partial-error/positions?limit=20"
      ) {
        return {
          run_id: "suite-run-partial-error",
          count: 0,
          items: [],
        };
      }
      throw new Error(`unexpected path ${path}`);
    });

    renderBacktestRunShell("suite-run-partial-error");

    expect(await screen.findByText("Unable to load backtest artifacts")).toBeInTheDocument();
    expect(screen.getByText("event stream unavailable")).toBeInTheDocument();
  });

  it("renders detail empty states when artifact lists are empty", async () => {
    mockedFetchJson.mockImplementation(async (path: string) => {
      if (path === "/backtests/suite-run-empty") {
        return {
          run_id: "suite-run-empty",
          manifest: {
            run_id: "suite-run-empty",
            suite_id: "suite-empty",
            dataset_id: "dataset-empty",
            strategy_id: "mean_reversion",
          },
          state: {
            cycle_id: "cycle-1",
            portfolio: {
              equity_usdc: 10000,
              gross_notional_usdc: 0,
              realized_pnl_usdc: 0,
              unrealized_pnl_usdc: 0,
            },
          },
          analysis: {
            run_id: "suite-run-empty",
            mode: "backtest",
            product_id: "MULTI_ASSET",
            strategy_id: "mean_reversion",
            started_at: "2026-03-22T04:00:00Z",
            ended_at: "2026-03-22T04:01:00Z",
            cycle_count: 1,
            starting_equity_usdc: 10000,
            ending_equity_usdc: 10000,
            realized_pnl_usdc: 0,
            unrealized_pnl_usdc: 0,
            total_pnl_usdc: 0,
            total_return_pct: 0,
            max_drawdown_usdc: 0,
            max_drawdown_pct: 0,
            turnover_usdc: 0,
            fill_count: 0,
            trade_count: 0,
            avg_abs_exposure_pct: 0,
            max_abs_exposure_pct: 0,
            decision_counts: {},
            equity_series: [],
            drawdown_series: [],
            exposure_series: [],
          },
        };
      }
      if (
        path === "/backtests/suite-run-empty/events?limit=20" ||
        path === "/backtests/suite-run-empty/fills?limit=20" ||
        path === "/backtests/suite-run-empty/positions?limit=20"
      ) {
        return {
          run_id: "suite-run-empty",
          count: 0,
          items: [],
        };
      }
      throw new Error(`unexpected path ${path}`);
    });

    renderBacktestRunShell("suite-run-empty");

    expect(await screen.findByText("No per-asset position snapshot was written for this backtest run.")).toBeInTheDocument();
    expect(screen.getByText("No asset-level decision payload was found in the latest event.")).toBeInTheDocument();
    expect(screen.getByText("This backtest run has no recorded fills yet.")).toBeInTheDocument();
    expect(screen.getByText("No event stream is available for this backtest run.")).toBeInTheDocument();
  });
});
