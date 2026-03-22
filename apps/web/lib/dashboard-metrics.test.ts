import { describe, expect, it } from "vitest";

import { buildAnalysisMetrics } from "@/lib/dashboard-metrics";


describe("buildAnalysisMetrics", () => {
  it("maps canonical analysis payloads into chart and KPI metrics", () => {
    const metrics = buildAnalysisMetrics({
      run_id: "run-1",
      mode: "paper",
      product_id: "BTC-PERP-INTX",
      strategy_id: "momentum",
      started_at: "2026-03-21T01:00:00Z",
      ended_at: "2026-03-21T02:00:00Z",
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
    });

    expect(metrics.totalReturnPct).toBe(0.0125);
    expect(metrics.totalPnlUsd).toBe(125);
    expect(metrics.cycleCount).toBe(12);
    expect(metrics.turnoverUsd).toBe(5200);
    expect(metrics.equitySeries).toEqual([
      { label: "cycle-1", value: 10000 },
      { label: "cycle-12", value: 10125 },
    ]);
    expect(metrics.decisionCounts).toEqual({
      filled: 3,
      below_rebalance_threshold: 9,
    });
  });

  it("leaves KPI values unknown when analysis is absent", () => {
    const metrics = buildAnalysisMetrics(null);

    expect(metrics.totalReturnPct).toBeNull();
    expect(metrics.totalPnlUsd).toBeNull();
    expect(metrics.tradeCount).toBeNull();
    expect(metrics.cycleCount).toBe(0);
    expect(metrics.equitySeries).toEqual([]);
    expect(metrics.decisionCounts).toEqual({});
  });
});
