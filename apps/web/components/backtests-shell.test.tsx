import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { BacktestRunShell } from "@/components/backtest-run-shell";
import { BacktestsShell } from "@/components/backtests-shell";


vi.mock("next/link", () => ({
  default: ({ href, children }: { href: string; children: React.ReactNode }) => <a href={href}>{children}</a>,
}));

describe("Backtest shells", () => {
  it("renders the backtests overview shell with permanent navigation", () => {
    render(<BacktestsShell />);

    expect(screen.getByText("Backtest Console")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /Overview/i })).toHaveAttribute("href", "/");
    expect(
      screen
        .getAllByRole("link", { name: /Backtests/i })
        .some((element) => element.getAttribute("href") === "/backtests")
    ).toBe(true);
    expect(screen.getByText("Launch, rank, inspect")).toBeInTheDocument();
  });

  it("renders the backtest run detail shell with a stable route model", () => {
    render(<BacktestRunShell runId="suite-run-1" />);

    expect(screen.getByText("Run Detail: suite-run-1")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /Back to Backtests/i })).toHaveAttribute("href", "/backtests");
    expect(screen.getByText("Per-asset inspection")).toBeInTheDocument();
  });
});
