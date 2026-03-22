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

describe("BacktestsShell", () => {
  beforeEach(() => {
    mockedFetchJson.mockReset();
    mockedStartBacktest.mockReset();
  });

  it("renders the launch console, suite ranking, and completed run table", async () => {
    mockedFetchJson.mockImplementation(async (path: string) => {
      if (path === "/backtests") {
        return {
          items: [
            {
              run_id: "run-2",
              created_at: "2026-03-22T06:00:00Z",
              suite_id: "suite-1",
              dataset_id: "dataset-1",
              product_id: "MULTI_ASSET",
              strategy_id: "momentum",
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
          active_job: null,
        };
      }
      if (path === "/backtest-suites") {
        return {
          items: [
            {
              suite_id: "suite-1",
              created_at: "2026-03-22T06:00:00Z",
              dataset_id: "dataset-1",
              products: ["BTC-PERP-INTX", "ETH-PERP-INTX"],
              strategies: ["momentum", "mean_reversion"],
              run_ids: ["run-2", "run-1"],
            },
          ],
          count: 1,
          active_job: null,
        };
      }
      if (path === "/backtest-suites/suite-1") {
        return {
          suite_id: "suite-1",
          created_at: "2026-03-22T06:00:00Z",
          dataset_id: "dataset-1",
          products: ["BTC-PERP-INTX", "ETH-PERP-INTX"],
          strategies: ["momentum", "mean_reversion"],
          run_ids: ["run-2", "run-1"],
          ranking_policy: "return desc",
          items: [
            {
              rank: 1,
              run_id: "run-2",
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
      throw new Error(`unexpected path ${path}`);
    });
    mockedStartBacktest.mockResolvedValue({
      job_id: "job-1",
      status: "running",
      pid: 4001,
      created_at: "2026-03-22T06:05:00Z",
      started_at: "2026-03-22T06:05:00Z",
      finished_at: null,
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
    expect(screen.getByText("Selected suite ranking")).toBeInTheDocument();
    expect(screen.getByText("Completed backtest runs")).toBeInTheDocument();
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
    expect(screen.getByText("backtest api unavailable")).toBeInTheDocument();
  });

  it("shows a validation warning when a datetime input is cleared", async () => {
    mockedFetchJson.mockImplementation(async (path: string) => {
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
});

describe("BacktestRunShell", () => {
  it("renders the backtest run detail shell with a stable route model", () => {
    render(<BacktestRunShell runId="suite-run-1" />);

    expect(screen.getByText("Run Detail: suite-run-1")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /Back to Backtests/i })).toHaveAttribute("href", "/backtests");
    expect(screen.getByText("Per-asset inspection")).toBeInTheDocument();
  });
});
