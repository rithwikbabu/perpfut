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

export function BacktestsShell() {
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
                Runtime Contract
              </div>
              <div className="mt-3 text-sm text-[var(--text)]">Bar-close signals, next-open fills</div>
              <p className="mt-2 text-sm leading-6 text-[var(--muted)]">
                Backtests reuse the same strategy registry as paper and live execution. Multi-asset allocation
                exists only inside the backtest runner.
              </p>
            </div>

            <div className="border border-[var(--border)] bg-[var(--bg-elevated)] p-4">
              <div className="mono text-[10px] uppercase tracking-[0.28em] text-[var(--warning)]">
                Console Scope
              </div>
              <div className="mt-3 text-sm text-[var(--text)]">Launch, rank, inspect</div>
              <p className="mt-2 text-sm leading-6 text-[var(--muted)]">
                This shell is permanent navigation scaffolding. The launch form, suite leaderboard, and run
                detail data wiring land in the next backtest frontend PRs.
              </p>
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
                Historical backtests with reusable production strategy code.
              </h1>
              <p className="mt-3 max-w-3xl text-sm leading-6 text-[var(--muted)]">
                Use this area to launch multi-asset backtest suites, compare strategy candidates on the
                canonical metrics contract, and drill into portfolio decisions without leaving the operator UI.
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
                <div className="mono text-[10px] text-[var(--accent)]">Artifacts</div>
                <div className="mt-2 text-sm text-[var(--text)]">runs/backtests</div>
              </div>
            </div>
          </header>

          <div className="grid gap-4 xl:grid-cols-[1.3fr_0.9fr]">
            <ShellPanel className="p-5">
              <ShellHeader eyebrow="Launch Surface" title="Backtest suite controls arrive next" action="BT-9" />
              <div className="signal-grid grid min-h-80 place-items-center border border-[var(--border)] bg-[var(--bg-elevated)] p-8 text-center">
                <div>
                  <div className="text-base font-medium text-[var(--text)]">Launch, list, and compare live here next.</div>
                  <p className="mt-3 max-w-xl text-sm leading-6 text-[var(--muted)]">
                    The next frontend step wires the launch form to <span className="mono">POST /api/backtests</span> and
                    renders suite rankings from <span className="mono">/api/backtest-suites</span>.
                  </p>
                </div>
              </div>
            </ShellPanel>

            <ShellPanel className="p-5">
              <ShellHeader eyebrow="Routes" title="Backtest drill-down is now addressable" />
              <div className="space-y-3 text-sm leading-6 text-[var(--muted)]">
                <div className="border border-[var(--border)] bg-[var(--bg-elevated)] p-4">
                  Overview route: <Link href="/backtests" className="text-[var(--accent)] underline decoration-[var(--border)] underline-offset-4">/backtests</Link>
                </div>
                <div className="border border-[var(--border)] bg-[var(--bg-elevated)] p-4">
                  Run detail route: <Link href="/backtests/demo-run" className="text-[var(--accent)] underline decoration-[var(--border)] underline-offset-4">/backtests/[runId]</Link>
                </div>
                <div className="border border-[var(--border)] bg-[var(--bg-elevated)] p-4">
                  Existing live operator dashboard remains at <Link href="/" className="text-[var(--accent)] underline decoration-[var(--border)] underline-offset-4">/</Link>.
                </div>
              </div>
            </ShellPanel>
          </div>
        </section>
      </div>
    </main>
  );
}
