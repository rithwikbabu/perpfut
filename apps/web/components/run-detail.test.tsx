import { render, screen } from "@testing-library/react";
import { SWRConfig } from "swr";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { RunDetail } from "@/components/run-detail";
import { ApiError } from "@/lib/perpfut-api";


vi.mock("next/link", () => ({
  default: ({ href, children }: { href: string; children: React.ReactNode }) => <a href={href}>{children}</a>,
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
      throw new Error(`unexpected path ${path}`);
    });

    renderRunDetail();

    expect(await screen.findByText("Run Detail: 20260322T020000000000Z_demo")).toBeInTheDocument();
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
});
