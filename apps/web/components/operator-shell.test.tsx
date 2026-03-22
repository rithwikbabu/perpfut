import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { SWRConfig } from "swr";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { OperatorShell } from "@/components/operator-shell";
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
    startPaperRun: vi.fn(),
    stopPaperRun: vi.fn(),
  };
});

const { fetchJson, startPaperRun, stopPaperRun } = await import("@/lib/perpfut-api");

const mockedFetchJson = vi.mocked(fetchJson);
const mockedStartPaperRun = vi.mocked(startPaperRun);
const mockedStopPaperRun = vi.mocked(stopPaperRun);

const overviewResponse = {
  mode: "paper" as const,
  generated_at: "2026-03-22T02:00:00Z",
  latest_run: {
    run_id: "20260322T020000000000Z_demo",
    created_at: "2026-03-22T02:00:00Z",
    mode: "paper",
    product_id: "BTC-PERP-INTX",
    resumed_from_run_id: null,
  },
  latest_state: {
    equity_usdc: 10125,
  },
  recent_events: [
    {
      event_type: "cycle",
      cycle_id: "cycle-2",
      signal: {
        target_position: 0.25,
        raw_value: 0.0042,
      },
      order_intent: {
        current_notional_usdc: 3000,
        target_notional_usdc: 5000,
      },
      position: {
        quantity: 0.15,
        mark_price: 103,
        entry_price: 100,
        collateral_usdc: 10000,
        realized_pnl_usdc: 125,
      },
    },
  ],
  recent_fills: [
    {
      cycle_id: "cycle-2",
      fill: {
        side: "BUY",
        quantity: 0.05,
        price: 103,
      },
    },
  ],
  recent_positions: [],
};

const runsResponse = {
  items: [overviewResponse.latest_run],
  count: 1,
};

function renderShell() {
  return render(
    <SWRConfig value={{ provider: () => new Map(), dedupingInterval: 0 }}>
      <OperatorShell />
    </SWRConfig>
  );
}

describe("OperatorShell", () => {
  beforeEach(() => {
    mockedFetchJson.mockReset();
    mockedStartPaperRun.mockReset();
    mockedStopPaperRun.mockReset();
  });

  it("shows a loading panel while operator data is still resolving", async () => {
    mockedFetchJson.mockImplementation(() => new Promise(() => undefined));

    renderShell();

    expect(await screen.findByText("Loading operator data")).toBeInTheDocument();
  });

  it("renders operator metrics and starts a paper run from the control panel", async () => {
    mockedFetchJson.mockImplementation(async (path: string) => {
      if (path.startsWith("/dashboard/overview")) {
        return overviewResponse;
      }
      if (path.startsWith("/runs?")) {
        return runsResponse;
      }
      if (path === "/paper-runs/active") {
        return {
          active: false,
          pid: null,
          started_at: null,
          run_id: null,
          product_id: null,
          iterations: null,
          interval_seconds: null,
          starting_collateral_usdc: null,
          log_path: null,
        };
      }
      throw new Error(`unexpected path ${path}`);
    });
    mockedStartPaperRun.mockResolvedValue({
      active: true,
      pid: 4321,
      started_at: "2026-03-22T02:01:00Z",
      run_id: null,
      product_id: "BTC-PERP-INTX",
      iterations: 1440,
      interval_seconds: 60,
      starting_collateral_usdc: 10000,
      log_path: "runs/control/paper.log",
    });

    renderShell();

    expect(await screen.findByText("Start or stop the local paper process")).toBeInTheDocument();
    expect(await screen.findByText("$10,125")).toBeInTheDocument();

    await userEvent.click(screen.getByRole("button", { name: "Start Paper Run" }));

    await waitFor(() =>
      expect(mockedStartPaperRun).toHaveBeenCalledWith({
        productId: "BTC-PERP-INTX",
        iterations: 1440,
        intervalSeconds: 60,
        startingCollateralUsdc: 10000,
      })
    );
    expect(await screen.findByText("Paper run started for BTC-PERP-INTX.")).toBeInTheDocument();
    expect(screen.getByText("PID 4321")).toBeInTheDocument();
  });

  it("stops an active paper run", async () => {
    mockedFetchJson.mockImplementation(async (path: string) => {
      if (path.startsWith("/dashboard/overview")) {
        return overviewResponse;
      }
      if (path.startsWith("/runs?")) {
        return runsResponse;
      }
      if (path === "/paper-runs/active") {
        return {
          active: true,
          pid: 4321,
          started_at: "2026-03-22T02:01:00Z",
          run_id: null,
          product_id: "BTC-PERP-INTX",
          iterations: 1440,
          interval_seconds: 60,
          starting_collateral_usdc: 10000,
          log_path: "runs/control/paper.log",
        };
      }
      throw new Error(`unexpected path ${path}`);
    });
    mockedStopPaperRun.mockResolvedValue({
      active: false,
      pid: null,
      started_at: null,
      run_id: null,
      product_id: "BTC-PERP-INTX",
      iterations: 1440,
      interval_seconds: 60,
      starting_collateral_usdc: 10000,
      log_path: "runs/control/paper.log",
    });

    renderShell();

    expect(await screen.findByText("Paper process active")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Stop Active Run" }));

    await waitFor(() => expect(mockedStopPaperRun).toHaveBeenCalledTimes(1));
    expect(await screen.findByText("Paper run stop signal completed.")).toBeInTheDocument();
  });

  it("surfaces control-plane conflicts from the start action", async () => {
    mockedFetchJson.mockImplementation(async (path: string) => {
      if (path.startsWith("/dashboard/overview")) {
        return overviewResponse;
      }
      if (path.startsWith("/runs?")) {
        return runsResponse;
      }
      if (path === "/paper-runs/active") {
        return {
          active: false,
          pid: null,
          started_at: null,
          run_id: null,
          product_id: null,
          iterations: null,
          interval_seconds: null,
          starting_collateral_usdc: null,
          log_path: null,
        };
      }
      throw new Error(`unexpected path ${path}`);
    });
    mockedStartPaperRun.mockRejectedValue(new ApiError("a paper run is already active", 409));

    renderShell();

    await screen.findByText("Start or stop the local paper process");
    await userEvent.click(screen.getByRole("button", { name: "Start Paper Run" }));

    expect(
      await screen.findByText("A paper run is already active. The control panel has refreshed the latest status.")
    ).toBeInTheDocument();
  });

  it("renders an API error panel when polling fails", async () => {
    mockedFetchJson.mockRejectedValue(new ApiError("control plane unavailable", 500));

    renderShell();

    expect(await screen.findByText("API unavailable")).toBeInTheDocument();
    expect(screen.getByText("control plane unavailable")).toBeInTheDocument();
  });
});
