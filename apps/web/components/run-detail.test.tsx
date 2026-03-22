import { render, screen } from "@testing-library/react";
import { SWRConfig } from "swr";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { RunDetail } from "@/components/run-detail";
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
  };
});

const { fetchJson } = await import("@/lib/perpfut-api");
const mockedFetchJson = vi.mocked(fetchJson);

function renderRunDetail() {
  return render(
    <SWRConfig value={{ provider: () => new Map(), dedupingInterval: 0 }}>
      <RunDetail runId="20260322T020000000000Z_demo" />
    </SWRConfig>
  );
}

describe("RunDetail", () => {
  beforeEach(() => {
    mockedFetchJson.mockReset();
  });

  it("renders manifest, state, fills, and events for a run", async () => {
    mockedFetchJson.mockImplementation(async (path: string) => {
      if (path.endsWith("/manifest")) {
        return {
          run_id: "20260322T020000000000Z_demo",
          data: {
            mode: "paper",
            product_id: "BTC-PERP-INTX",
          },
        };
      }
      if (path.endsWith("/state")) {
        return {
          run_id: "20260322T020000000000Z_demo",
          data: {
            equity_usdc: 10125,
            cycle_id: "cycle-2",
            signal: {
              strategy: "momentum",
              raw_value: 0.0042,
              target_position: 0.25,
            },
            risk_decision: {
              target_after_risk: 0.25,
              current_position: 0.15,
              delta_notional_usdc: 2000,
            },
            execution_summary: {
              action: "skipped",
              reason_code: "below_rebalance_threshold",
              reason_message: "Delta position 0.0200 is below the rebalance threshold of 0.1000.",
              summary: "Skipped rebalancing: delta position remained below threshold.",
            },
            no_trade_reason: {
              code: "below_rebalance_threshold",
              message: "Delta position 0.0200 is below the rebalance threshold of 0.1000.",
            },
          },
        };
      }
      if (path.includes("/fills")) {
        return {
          run_id: "20260322T020000000000Z_demo",
          count: 1,
          items: [
            {
              cycle_id: "cycle-2",
              fill: {
                side: "BUY",
                quantity: 0.05,
                price: 103,
              },
            },
          ],
        };
      }
      if (path.includes("/positions")) {
        return {
          run_id: "20260322T020000000000Z_demo",
          count: 1,
          items: [
            {
              cycle_id: "cycle-2",
              position: {
                quantity: 0.15,
              },
            },
          ],
        };
      }
      if (path.includes("/events")) {
        return {
          run_id: "20260322T020000000000Z_demo",
          count: 1,
          items: [
            {
              event_type: "cycle",
              cycle_id: "cycle-2",
              execution_summary: {
                summary: "Skipped rebalancing: delta position remained below threshold.",
              },
            },
          ],
        };
      }
      if (path.includes("/analysis")) {
        return {
          run_id: "20260322T020000000000Z_demo",
          mode: "paper",
          product_id: "BTC-PERP-INTX",
          strategy_id: "momentum",
          started_at: "2026-03-22T02:00:00Z",
          ended_at: "2026-03-22T02:10:00Z",
          cycle_count: 12,
          starting_equity_usdc: 10000,
          ending_equity_usdc: 10125,
          realized_pnl_usdc: 80,
          unrealized_pnl_usdc: 45,
          total_pnl_usdc: 125,
          total_return_pct: 0.0125,
          max_drawdown_usdc: 40,
          max_drawdown_pct: 0.004,
          turnover_usdc: 5200,
          fill_count: 3,
          trade_count: 3,
          avg_abs_exposure_pct: 0.22,
          max_abs_exposure_pct: 0.35,
          decision_counts: {
            filled: 3,
            below_rebalance_threshold: 9,
          },
          equity_series: [
            { label: "cycle-1", value: 10000 },
            { label: "cycle-12", value: 10125 },
          ],
          drawdown_series: [
            { label: "cycle-1", value: 0 },
            { label: "cycle-12", value: 40 },
          ],
          exposure_series: [
            { label: "cycle-1", value: 0.1 },
            { label: "cycle-12", value: 0.22 },
          ],
        };
      }
      throw new Error(`unexpected path ${path}`);
    });

    renderRunDetail();

    expect(await screen.findByText("Run Detail: 20260322T020000000000Z_demo")).toBeInTheDocument();
    expect(screen.getByText("Canonical Analysis Summary")).toBeInTheDocument();
    expect(screen.getByText("+1.25%")).toBeInTheDocument();
    expect(screen.getByText("Absolute Exposure Timeline")).toBeInTheDocument();
    expect(screen.getByText("Recent Fill Tape")).toBeInTheDocument();
    expect(screen.getByText("BUY")).toBeInTheDocument();
    expect(screen.getByText("Latest Decision Snapshot")).toBeInTheDocument();
    expect(
      screen.getAllByText("Skipped rebalancing: delta position remained below threshold.").length
    ).toBeGreaterThan(0);
    expect(screen.getByText("Operator Event Stream")).toBeInTheDocument();
  });

  it("renders an error state when any artifact request fails", async () => {
    mockedFetchJson.mockRejectedValue(new ApiError("run artifacts unavailable", 500));

    renderRunDetail();

    expect(await screen.findByText("Unable to load run artifacts")).toBeInTheDocument();
    expect(screen.getByText("run artifacts unavailable")).toBeInTheDocument();
  });

  it("renders the empty decision fallback for older checkpoints without structured telemetry", async () => {
    mockedFetchJson.mockImplementation(async (path: string) => {
      if (path.endsWith("/manifest")) {
        return {
          run_id: "20260322T020000000000Z_demo",
          data: {
            mode: "paper",
            product_id: "BTC-PERP-INTX",
          },
        };
      }
      if (path.endsWith("/state")) {
        return {
          run_id: "20260322T020000000000Z_demo",
          data: {
            equity_usdc: 10125,
          },
        };
      }
      if (path.includes("/fills") || path.includes("/positions") || path.includes("/events")) {
        return {
          run_id: "20260322T020000000000Z_demo",
          count: 0,
          items: [],
        };
      }
      if (path.includes("/analysis")) {
        return {
          run_id: "20260322T020000000000Z_demo",
          mode: "paper",
          product_id: "BTC-PERP-INTX",
          strategy_id: null,
          started_at: "2026-03-22T02:00:00Z",
          ended_at: "2026-03-22T02:00:00Z",
          cycle_count: 0,
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
        };
      }
      throw new Error(`unexpected path ${path}`);
    });

    renderRunDetail();

    expect(await screen.findByText("Latest Decision Snapshot")).toBeInTheDocument();
    expect(
      screen.getByText("No normalized decision summary is available in this checkpoint yet.")
    ).toBeInTheDocument();
  });

  it("keeps the run detail readable when canonical analysis is unavailable", async () => {
    mockedFetchJson.mockImplementation(async (path: string) => {
      if (path.endsWith("/manifest")) {
        return {
          run_id: "20260322T020000000000Z_demo",
          data: {
            mode: "paper",
            product_id: "BTC-PERP-INTX",
          },
        };
      }
      if (path.endsWith("/state")) {
        return {
          run_id: "20260322T020000000000Z_demo",
          data: {
            equity_usdc: 10125,
            execution_summary: {
              action: "filled",
              reason_code: "filled",
              reason_message: "Cycle placed and filled a rebalance order.",
              summary: "Filled a rebalance order toward the target position.",
            },
          },
        };
      }
      if (path.includes("/fills") || path.includes("/positions") || path.includes("/events")) {
        return {
          run_id: "20260322T020000000000Z_demo",
          count: 0,
          items: [],
        };
      }
      if (path.includes("/analysis")) {
        throw new ApiError("analysis inputs not found", 404);
      }
      throw new Error(`unexpected path ${path}`);
    });

    renderRunDetail();

    expect(await screen.findByText("Run Detail: 20260322T020000000000Z_demo")).toBeInTheDocument();
    expect(screen.getByText("Canonical Analysis Unavailable")).toBeInTheDocument();
    expect(screen.getByText("analysis inputs not found")).toBeInTheDocument();
    expect(screen.getByText("Latest Decision Snapshot")).toBeInTheDocument();
  });
});
