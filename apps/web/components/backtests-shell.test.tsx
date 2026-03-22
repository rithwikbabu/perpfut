import { render, screen, waitFor } from "@testing-library/react";
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
    startBacktest: vi.fn(),
  };
});

const { fetchJson, startBacktest } = await import("@/lib/perpfut-api");

const mockedFetchJson = vi.mocked(fetchJson);
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

describe("BacktestsShell", () => {
  beforeEach(() => {
    mockedFetchJson.mockReset();
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
    expect(screen.getByText("Selected suite ranking")).toBeInTheDocument();
    expect(screen.getByText("Completed backtest runs")).toBeInTheDocument();
    expect((await screen.findAllByText("Completed strategy 1 of 2: momentum")).length).toBeGreaterThan(0);
    expect(screen.getAllByText("1.87").length).toBeGreaterThan(0);
    expect(screen.getByRole("link", { name: "run-2" })).toHaveAttribute("href", "/backtests/run-2");

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
      if (path === "/backtests" || path === "/backtest-suites" || path === "/datasets") {
        return new Promise(() => {});
      }
      throw new Error(`unexpected path ${path}`);
    });

    renderBacktestsShell();

    expect((await screen.findAllByText("Loading cached datasets.")).length).toBeGreaterThan(0);
    expect(await screen.findByText("Loading completed backtest suites.")).toBeInTheDocument();
    expect(screen.getByText("Loading completed backtest runs.")).toBeInTheDocument();
    expect(screen.getByText("Select a suite to rank strategy candidates.")).toBeInTheDocument();
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
      throw new Error(`unexpected path ${path}`);
    });

    renderBacktestsShell();

    expect((await screen.findAllByText("No cached datasets yet.")).length).toBeGreaterThan(0);
    expect(await screen.findByText("No completed backtest suites yet.")).toBeInTheDocument();
    expect(screen.getByText("Select a suite to rank strategy candidates.")).toBeInTheDocument();
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
      throw new Error(`unexpected path ${path}`);
    });

    renderBacktestsShell();

    expect((await screen.findAllByText("dataset registry unavailable")).length).toBeGreaterThan(0);
    expect(screen.queryByText("No cached datasets yet.")).not.toBeInTheDocument();
    expect(screen.getByText("No completed backtest suites yet.")).toBeInTheDocument();
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
