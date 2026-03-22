import Link from "next/link";


type StatCardProps = {
  label: string;
  value: string;
  change: string;
  tone?: "neutral" | "accent" | "warning";
};

function StatCard({ label, value, change, tone = "neutral" }: StatCardProps) {
  const changeClass =
    tone === "accent"
      ? "text-[var(--accent)]"
      : tone === "warning"
        ? "text-[var(--warning)]"
        : "text-[var(--muted)]";

  return (
    <div className="panel flex min-h-36 flex-col justify-between p-5">
      <div className="flex items-center justify-between text-[11px] uppercase tracking-[0.28em] text-[var(--muted)]">
        <span>{label}</span>
        <span className="mono text-[10px] text-[var(--border-strong)]">LIVE VIEW</span>
      </div>
      <div>
        <div className="mono text-3xl font-semibold tracking-tight text-[var(--text)]">{value}</div>
        <div className={`mt-2 text-sm ${changeClass}`}>{change}</div>
      </div>
    </div>
  );
}

function SectionHeader({
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

export function OperatorShell() {
  return (
    <main className="min-h-screen px-4 py-4 text-[var(--text)] sm:px-6 lg:px-8">
      <div className="mx-auto grid max-w-[1680px] gap-4 lg:grid-cols-[260px_minmax(0,1fr)]">
        <aside className="panel flex min-h-[calc(100vh-2rem)] flex-col justify-between p-5">
          <div>
            <div className="mono text-[11px] uppercase tracking-[0.34em] text-[var(--accent)]">perpfut</div>
            <div className="mt-3 text-2xl font-semibold tracking-tight">Operator Console</div>
            <p className="mt-3 max-w-xs text-sm leading-6 text-[var(--muted)]">
              Local-first control surface for paper mode monitoring, run inspection, and future
              live-readiness workflows.
            </p>
            <div className="mt-8 space-y-2">
              {["Overview", "Runs", "Paper Control", "Live Readiness"].map((item, index) => (
                <Link
                  key={item}
                  href={index === 0 ? "/" : "#"}
                  className={`flex items-center justify-between border px-3 py-3 text-sm tracking-wide transition ${
                    index === 0
                      ? "border-[var(--border-strong)] bg-[rgba(84,191,255,0.08)]"
                      : "border-transparent bg-transparent text-[var(--muted)] hover:border-[var(--border)] hover:text-[var(--text)]"
                  }`}
                >
                  <span>{item}</span>
                  <span className="mono text-[11px]">{String(index + 1).padStart(2, "0")}</span>
                </Link>
              ))}
            </div>
          </div>

          <div className="border border-[var(--border)] bg-[var(--bg-elevated)] p-4">
            <div className="mono text-[10px] uppercase tracking-[0.28em] text-[var(--warning)]">
              Design Intent
            </div>
            <p className="mt-3 text-sm leading-6 text-[var(--muted)]">
              Dense, dark, and operational. This shell favors legibility, state visibility, and
              calm signal over decorative chrome.
            </p>
          </div>
        </aside>

        <section className="space-y-4">
          <header className="panel panel-strong flex flex-col gap-5 p-5 lg:flex-row lg:items-end lg:justify-between">
            <div>
              <div className="mono text-[11px] uppercase tracking-[0.34em] text-[var(--accent)]">
                Operator Overview
              </div>
              <h1 className="mt-3 max-w-3xl text-3xl font-semibold tracking-tight">
                Monitor paper execution with a single-screen command deck.
              </h1>
              <p className="mt-3 max-w-3xl text-sm leading-6 text-[var(--muted)]">
                The data wiring lands in later issues. This first pass establishes the visual
                system, information hierarchy, and operator shell the live dashboard will sit in.
              </p>
            </div>
            <div className="grid gap-2 text-xs uppercase tracking-[0.22em] text-[var(--muted)] sm:grid-cols-3">
              <div className="border border-[var(--border)] px-3 py-3">
                <div className="mono text-[10px] text-[var(--accent)]">Mode</div>
                <div className="mt-2 text-sm text-[var(--text)]">Paper</div>
              </div>
              <div className="border border-[var(--border)] px-3 py-3">
                <div className="mono text-[10px] text-[var(--accent)]">Product</div>
                <div className="mt-2 text-sm text-[var(--text)]">BTC-PERP-INTX</div>
              </div>
              <div className="border border-[var(--border)] px-3 py-3">
                <div className="mono text-[10px] text-[var(--accent)]">Status</div>
                <div className="mt-2 text-sm text-[var(--warning)]">Awaiting API feed</div>
              </div>
            </div>
          </header>

          <div className="grid gap-4 xl:grid-cols-4 md:grid-cols-2">
            <StatCard label="Equity" value="$10,240" change="+2.4% simulated" tone="accent" />
            <StatCard label="Realized PnL" value="+$184" change="Directionally positive" tone="accent" />
            <StatCard label="Net Position" value="0.21 BTC" change="Long bias / clipped" />
            <StatCard label="Risk State" value="Nominal" change="No drawdown halt active" tone="warning" />
          </div>

          <div className="grid gap-4 xl:grid-cols-[1.45fr_1fr]">
            <section className="panel p-5">
              <SectionHeader eyebrow="Signal" title="Equity And PnL Trajectory" action="placeholder series" />
              <div className="signal-grid flex h-80 items-end gap-3 overflow-hidden border border-[var(--border)] px-4 py-5">
                {[24, 32, 29, 41, 46, 44, 52, 61, 64, 73, 70, 82].map((value, index) => (
                  <div key={value + index} className="flex h-full flex-1 items-end">
                    <div
                      className="w-full bg-gradient-to-t from-[rgba(84,191,255,0.95)] to-[rgba(143,214,255,0.15)]"
                      style={{ height: `${value}%` }}
                    />
                  </div>
                ))}
              </div>
            </section>

            <section className="panel p-5">
              <SectionHeader eyebrow="Positioning" title="Target Versus Current Exposure" />
              <div className="signal-grid grid h-80 place-items-center border border-[var(--border)] p-6">
                <div className="relative flex h-64 w-64 items-center justify-center rounded-full border border-[var(--border)]">
                  <div className="absolute inset-5 rounded-full border border-dashed border-[var(--border)]" />
                  <div className="absolute inset-10 rounded-full border border-[var(--border)]" />
                  <div className="absolute h-48 w-[2px] -rotate-12 bg-[rgba(143,214,255,0.18)]" />
                  <div className="absolute w-52 border-t border-dashed border-[rgba(143,214,255,0.14)]" />
                  <div className="absolute bottom-7 left-1/2 h-16 w-16 -translate-x-1/2 rounded-full border border-[var(--border-strong)] bg-[rgba(84,191,255,0.12)]" />
                  <div className="z-10 text-center">
                    <div className="mono text-[10px] uppercase tracking-[0.28em] text-[var(--accent)]">
                      Target / Current
                    </div>
                    <div className="mt-3 text-4xl font-semibold tracking-tight">0.38 / 0.21</div>
                    <div className="mt-2 text-sm text-[var(--muted)]">normalized position</div>
                  </div>
                </div>
              </div>
            </section>
          </div>

          <div className="grid gap-4 xl:grid-cols-2">
            <section className="panel p-5">
              <SectionHeader eyebrow="Execution Tape" title="Recent Fills" action="mocked rows" />
              <div className="overflow-hidden border border-[var(--border)]">
                <table className="w-full border-collapse text-left text-sm">
                  <thead className="bg-[rgba(84,191,255,0.06)] text-[var(--muted)]">
                    <tr>
                      {["Time", "Side", "Size", "Price", "Slippage"].map((cell) => (
                        <th key={cell} className="px-4 py-3 font-medium">
                          {cell}
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody className="mono">
                    {[
                      ["12:01:00", "BUY", "0.024", "70120.2", "+3.0bps"],
                      ["12:04:00", "BUY", "0.011", "70188.1", "+3.0bps"],
                      ["12:10:00", "SELL", "0.008", "70302.4", "+3.0bps"],
                    ].map((row) => (
                      <tr key={row.join("-")} className="border-t border-[var(--border)] text-[var(--text)]">
                        {row.map((cell, index) => (
                          <td
                            key={cell}
                            className={`px-4 py-3 ${index === 1 ? "text-[var(--accent)]" : "text-[var(--muted)]"}`}
                          >
                            {cell}
                          </td>
                        ))}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </section>

            <section className="panel p-5">
              <SectionHeader eyebrow="Events" title="Operator Feed" action="mocked rows" />
              <div className="space-y-3">
                {[
                  ["cycle", "Signal updated to 0.38 target position", "12:10:00"],
                  ["risk", "Rebalance cleared threshold and minimum notional", "12:10:00"],
                  ["telemetry", "Run artifacts appended under runs/<timestamp>_<sha>", "12:10:01"],
                ].map(([tag, message, time]) => (
                  <div
                    key={message}
                    className="border border-[var(--border)] bg-[var(--bg-elevated)] px-4 py-4"
                  >
                    <div className="flex items-center justify-between gap-4">
                      <span className="mono text-[10px] uppercase tracking-[0.26em] text-[var(--accent)]">
                        {tag}
                      </span>
                      <span className="mono text-[11px] text-[var(--muted)]">{time}</span>
                    </div>
                    <p className="mt-3 text-sm leading-6 text-[var(--text)]">{message}</p>
                  </div>
                ))}
              </div>
            </section>
          </div>
        </section>
      </div>
    </main>
  );
}
