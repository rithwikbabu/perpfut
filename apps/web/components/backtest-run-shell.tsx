import Link from "next/link";

import { ConsoleNav } from "@/components/console-nav";


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

export function BacktestRunShell({ runId }: { runId: string }) {
  return (
    <main className="min-h-screen px-4 py-4 text-[var(--text)] sm:px-6 lg:px-8">
      <div className="mx-auto grid max-w-[1680px] gap-4 lg:grid-cols-[260px_minmax(0,1fr)]">
        <aside className="panel flex min-h-[calc(100vh-2rem)] flex-col justify-between p-5">
          <div>
            <div className="mono text-[11px] uppercase tracking-[0.34em] text-[var(--accent)]">perpfut</div>
            <div className="mt-3 text-2xl font-semibold tracking-tight">Backtest Detail</div>
            <p className="mt-3 max-w-xs text-sm leading-6 text-[var(--muted)]">
              Drill into a single backtest run with the same operator styling used across the console.
            </p>
            <ConsoleNav active="backtests" />
          </div>

          <div className="space-y-4">
            <div className="border border-[var(--border)] bg-[var(--bg-elevated)] p-4">
              <div className="mono text-[10px] uppercase tracking-[0.28em] text-[var(--warning)]">
                Selected Run
              </div>
              <div className="mt-3 text-sm text-[var(--text)]">{runId}</div>
              <p className="mt-2 text-sm leading-6 text-[var(--muted)]">
                This permanent route shell is in place. The full analysis, fill tape, and decision drill-down
                wiring land in the next run-detail PR.
              </p>
            </div>
          </div>
        </aside>

        <section className="space-y-4">
          <header className="panel panel-strong flex flex-col gap-5 p-5 lg:flex-row lg:items-end lg:justify-between">
            <div>
              <div className="mono text-[11px] uppercase tracking-[0.34em] text-[var(--accent)]">
                Backtest Run
              </div>
              <h1 className="mt-3 max-w-3xl text-3xl font-semibold tracking-tight">
                Run Detail: {runId}
              </h1>
              <p className="mt-3 max-w-3xl text-sm leading-6 text-[var(--muted)]">
                This route will render canonical analysis, decisions, fills, and per-asset portfolio views
                from the backtest API. The shell exists now so the navigation and URL model are stable.
              </p>
            </div>
            <Link
              href="/backtests"
              className="inline-flex items-center border border-[var(--border)] px-4 py-3 text-xs uppercase tracking-[0.24em] text-[var(--muted)] transition hover:border-[var(--border-strong)] hover:text-[var(--text)]"
            >
              Back to Backtests
            </Link>
          </header>

          <div className="grid gap-4 lg:grid-cols-3">
            <ShellPanel className="p-5">
              <ShellHeader eyebrow="Analysis" title="Canonical metrics panel" action="BT-10" />
              <div className="min-h-48 border border-[var(--border)] bg-[var(--bg-elevated)] p-5 text-sm leading-6 text-[var(--muted)]">
                Equity, drawdown, turnover, and exposure summaries will render here from the canonical
                analysis contract.
              </div>
            </ShellPanel>

            <ShellPanel className="p-5">
              <ShellHeader eyebrow="Decisions" title="Decision drill-down" action="BT-10" />
              <div className="min-h-48 border border-[var(--border)] bg-[var(--bg-elevated)] p-5 text-sm leading-6 text-[var(--muted)]">
                Cycle-level explanations and no-trade reasons for the selected backtest run land in the next
                frontend step.
              </div>
            </ShellPanel>

            <ShellPanel className="p-5">
              <ShellHeader eyebrow="Assets" title="Per-asset inspection" action="BT-10" />
              <div className="min-h-48 border border-[var(--border)] bg-[var(--bg-elevated)] p-5 text-sm leading-6 text-[var(--muted)]">
                Per-asset positions, fills, and contribution views are reserved for the full detail page.
              </div>
            </ShellPanel>
          </div>
        </section>
      </div>
    </main>
  );
}
