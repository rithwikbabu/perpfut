"use client";

import Link from "next/link";
import useSWR from "swr";
import {
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import { buildDashboardMetrics, formatMoney, formatSigned, formatTimestamp } from "@/lib/dashboard-metrics";
import { fetchJson, type DashboardOverviewResponse, type RunsListResponse } from "@/lib/perpfut-api";


function Panel({
  children,
  className = "",
}: {
  children: React.ReactNode;
  className?: string;
}) {
  return <section className={`panel ${className}`}>{children}</section>;
}

function StatCard({
  label,
  value,
  change,
  tone = "neutral",
}: {
  label: string;
  value: string;
  change: string;
  tone?: "neutral" | "accent" | "warning";
}) {
  const changeClass =
    tone === "accent"
      ? "text-[var(--accent)]"
      : tone === "warning"
        ? "text-[var(--warning)]"
        : "text-[var(--muted)]";

  return (
    <Panel className="flex min-h-36 flex-col justify-between p-5">
      <div className="flex items-center justify-between text-[11px] uppercase tracking-[0.28em] text-[var(--muted)]">
        <span>{label}</span>
        <span className="mono text-[10px] text-[var(--border-strong)]">POLL 2S</span>
      </div>
      <div>
        <div className="mono text-3xl font-semibold tracking-tight text-[var(--text)]">{value}</div>
        <div className={`mt-2 text-sm ${changeClass}`}>{change}</div>
      </div>
    </Panel>
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

function LoadingPanel({ label }: { label: string }) {
  return (
    <Panel className="p-5">
      <SectionHeader eyebrow={label} title="Loading operator data" />
      <div className="signal-grid grid h-72 place-items-center border border-[var(--border)] text-sm text-[var(--muted)]">
        Waiting for the local API proxy.
      </div>
    </Panel>
  );
}

function ErrorPanel({ message }: { message: string }) {
  return (
    <Panel className="p-5">
      <SectionHeader eyebrow="Connection" title="API unavailable" />
      <div className="border border-[rgba(255,109,123,0.38)] bg-[rgba(255,109,123,0.08)] p-4 text-sm leading-6 text-[var(--danger)]">
        {message}
      </div>
    </Panel>
  );
}

function EmptyPanel() {
  return (
    <Panel className="p-5">
      <SectionHeader eyebrow="Runs" title="No paper runs yet" />
      <div className="border border-[var(--border)] bg-[var(--bg-elevated)] p-5 text-sm leading-6 text-[var(--muted)]">
        Start a paper run from the CLI for now, then this dashboard will populate from the
        artifact history under <span className="mono">runs/</span>.
      </div>
    </Panel>
  );
}

function EventMessage(event: Record<string, unknown>): string {
  if (typeof event.reason === "string") {
    return event.reason;
  }
  const signal = asRecord(event.signal);
  if (signal && typeof signal.target_position === "number") {
    return `target ${signal.target_position.toFixed(2)} / raw ${(signal.raw_value as number | undefined)?.toFixed(4) ?? "--"}`;
  }
  return "artifact event";
}

function asRecord(value: unknown): Record<string, unknown> | null {
  return value !== null && typeof value === "object" && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : null;
}

export function OperatorShell() {
  const overview = useSWR<DashboardOverviewResponse>(
    "/dashboard/overview?mode=paper&limit=24",
    (path) => fetchJson(path),
    { refreshInterval: 2_000 }
  );
  const runs = useSWR<RunsListResponse>(
    "/runs?mode=paper&limit=6",
    (path) => fetchJson(path),
    { refreshInterval: 2_000 }
  );

  const overviewData = overview.data;
  const metrics = overviewData ? buildDashboardMetrics(overviewData) : null;
  const latestRun = overviewData?.latest_run;
  const isLoading = overview.isLoading || runs.isLoading;
  const error = overview.error ?? runs.error;

  return (
    <main className="min-h-screen px-4 py-4 text-[var(--text)] sm:px-6 lg:px-8">
      <div className="mx-auto grid max-w-[1680px] gap-4 lg:grid-cols-[260px_minmax(0,1fr)]">
        <aside className="panel flex min-h-[calc(100vh-2rem)] flex-col justify-between p-5">
          <div>
            <div className="mono text-[11px] uppercase tracking-[0.34em] text-[var(--accent)]">perpfut</div>
            <div className="mt-3 text-2xl font-semibold tracking-tight">Operator Console</div>
            <p className="mt-3 max-w-xs text-sm leading-6 text-[var(--muted)]">
              Local-first monitoring for paper execution, artifact inspection, and later operator
              controls.
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
              Latest Run
            </div>
            {latestRun ? (
              <Link href={`/runs/${latestRun.run_id}`} className="mt-3 block text-sm text-[var(--text)] underline decoration-[var(--border)] underline-offset-4">
                {latestRun.run_id}
              </Link>
            ) : (
              <div className="mt-3 text-sm text-[var(--text)]">No run detected</div>
            )}
            <p className="mt-2 text-sm leading-6 text-[var(--muted)]">
              {latestRun
                ? `${latestRun.mode?.toUpperCase() ?? "UNKNOWN"} · ${latestRun.product_id ?? "Unknown product"}`
                : "Waiting for the first matching paper artifact set."}
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
                Paper execution monitoring with live artifact polling.
              </h1>
              <p className="mt-3 max-w-3xl text-sm leading-6 text-[var(--muted)]">
                This dashboard reads from the Python operator API every two seconds and surfaces
                latest-run telemetry, recent fills, and cycle-level positioning.
              </p>
            </div>
            <div className="grid gap-2 text-xs uppercase tracking-[0.22em] text-[var(--muted)] sm:grid-cols-3">
              <div className="border border-[var(--border)] px-3 py-3">
                <div className="mono text-[10px] text-[var(--accent)]">Mode</div>
                <div className="mt-2 text-sm text-[var(--text)]">Paper</div>
              </div>
              <div className="border border-[var(--border)] px-3 py-3">
                <div className="mono text-[10px] text-[var(--accent)]">Product</div>
                <div className="mt-2 text-sm text-[var(--text)]">{latestRun?.product_id ?? "--"}</div>
              </div>
              <div className="border border-[var(--border)] px-3 py-3">
                <div className="mono text-[10px] text-[var(--accent)]">Updated</div>
                <div className="mt-2 text-sm text-[var(--text)]">
                  {overviewData ? formatTimestamp(overviewData.generated_at) : "--"}
                </div>
              </div>
            </div>
          </header>

          {error ? <ErrorPanel message={error.message} /> : null}
          {!error && isLoading ? <LoadingPanel label="Overview" /> : null}
          {!error && !isLoading && !latestRun ? <EmptyPanel /> : null}

          {!error && !isLoading && latestRun && metrics && overviewData ? (
            <>
              <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
                <StatCard
                  label="Equity"
                  value={formatMoney(metrics.equityUsd)}
                  change={`${metrics.equitySeries.length} cycle points`}
                  tone="accent"
                />
                <StatCard
                  label="Realized PnL"
                  value={formatMoney(metrics.realizedPnlUsd)}
                  change={`${formatSigned(metrics.unrealizedPnlUsd)} unrealized`}
                  tone="accent"
                />
                <StatCard
                  label="Net Position"
                  value={metrics.quantity === null ? "--" : `${metrics.quantity.toFixed(4)} base`}
                  change={`target ${formatSigned(metrics.targetPosition, 3)}`}
                />
                <StatCard
                  label="Signal"
                  value={formatSigned(metrics.lastSignalRaw, 4)}
                  change={`${metrics.fillCount} fills / ${metrics.eventCount} events`}
                  tone="warning"
                />
              </div>

              <div className="grid gap-4 xl:grid-cols-[1.45fr_1fr]">
                <Panel className="p-5">
                  <SectionHeader
                    eyebrow="Signal"
                    title="Equity And Realized PnL"
                    action={`${metrics.equitySeries.length} plotted cycles`}
                  />
                  <div className="signal-grid h-80 border border-[var(--border)] p-3">
                    <ResponsiveContainer width="100%" height="100%">
                      <LineChart data={metrics.equitySeries}>
                        <CartesianGrid stroke="rgba(143,214,255,0.1)" vertical={false} />
                        <XAxis
                          dataKey="label"
                          tick={{ fill: "#90a4bf", fontSize: 11 }}
                          tickLine={false}
                          axisLine={false}
                        />
                        <YAxis
                          tick={{ fill: "#90a4bf", fontSize: 11 }}
                          tickLine={false}
                          axisLine={false}
                          width={80}
                        />
                        <Tooltip
                          contentStyle={{
                            border: "1px solid rgba(135, 162, 196, 0.22)",
                            background: "rgba(8, 12, 20, 0.96)",
                            color: "#ecf4ff",
                          }}
                        />
                        <Line type="monotone" dataKey="equity" stroke="#8fd6ff" strokeWidth={2.5} dot={false} />
                        <Line
                          type="monotone"
                          dataKey="realizedPnl"
                          stroke="#f1bb67"
                          strokeWidth={2}
                          dot={false}
                        />
                      </LineChart>
                    </ResponsiveContainer>
                  </div>
                </Panel>

                <Panel className="p-5">
                  <SectionHeader
                    eyebrow="Positioning"
                    title="Target Versus Current Exposure"
                    action="derived from cycle artifacts"
                  />
                  <div className="signal-grid h-80 border border-[var(--border)] p-3">
                    <ResponsiveContainer width="100%" height="100%">
                      <LineChart data={metrics.positionSeries}>
                        <CartesianGrid stroke="rgba(143,214,255,0.1)" vertical={false} />
                        <XAxis
                          dataKey="label"
                          tick={{ fill: "#90a4bf", fontSize: 11 }}
                          tickLine={false}
                          axisLine={false}
                        />
                        <YAxis
                          domain={[-1, 1]}
                          tick={{ fill: "#90a4bf", fontSize: 11 }}
                          tickLine={false}
                          axisLine={false}
                          width={40}
                        />
                        <Tooltip
                          contentStyle={{
                            border: "1px solid rgba(135, 162, 196, 0.22)",
                            background: "rgba(8, 12, 20, 0.96)",
                            color: "#ecf4ff",
                          }}
                        />
                        <Line type="monotone" dataKey="target" stroke="#8fd6ff" strokeWidth={2.5} dot={false} />
                        <Line
                          type="monotone"
                          dataKey="current"
                          stroke="#9bf6cf"
                          strokeWidth={2}
                          dot={false}
                        />
                      </LineChart>
                    </ResponsiveContainer>
                  </div>
                </Panel>
              </div>

              <div className="grid gap-4 xl:grid-cols-[1.1fr_0.9fr]">
                <Panel className="p-5">
                  <SectionHeader eyebrow="Runs" title="Latest Paper Runs" action={`${runs.data?.count ?? 0} loaded`} />
                  <div className="overflow-hidden border border-[var(--border)]">
                    <table className="w-full border-collapse text-left text-sm">
                      <thead className="bg-[rgba(84,191,255,0.06)] text-[var(--muted)]">
                        <tr>
                          {["Run", "Mode", "Product", "Created"].map((cell) => (
                            <th key={cell} className="px-4 py-3 font-medium">
                              {cell}
                            </th>
                          ))}
                        </tr>
                      </thead>
                      <tbody className="mono">
                        {(runs.data?.items ?? []).map((run) => (
                          <tr key={run.run_id} className="border-t border-[var(--border)]">
                            <td className="px-4 py-3 text-[var(--text)]">
                              <Link href={`/runs/${run.run_id}`} className="underline decoration-[var(--border)] underline-offset-4">
                                {run.run_id}
                              </Link>
                            </td>
                            <td className="px-4 py-3 text-[var(--accent)]">{run.mode ?? "--"}</td>
                            <td className="px-4 py-3 text-[var(--muted)]">{run.product_id ?? "--"}</td>
                            <td className="px-4 py-3 text-[var(--muted)]">{formatTimestamp(run.created_at)}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </Panel>

                <Panel className="p-5">
                  <SectionHeader eyebrow="Execution Tape" title="Recent Fills" action={`${overviewData.recent_fills.length} rows`} />
                  <div className="overflow-hidden border border-[var(--border)]">
                    <table className="w-full border-collapse text-left text-sm">
                      <thead className="bg-[rgba(84,191,255,0.06)] text-[var(--muted)]">
                        <tr>
                          {["Cycle", "Side", "Qty", "Price"].map((cell) => (
                            <th key={cell} className="px-4 py-3 font-medium">
                              {cell}
                            </th>
                          ))}
                        </tr>
                      </thead>
                      <tbody className="mono">
                        {overviewData.recent_fills.map((row, index) => {
                          const fill = asRecord(row.fill);
                          return (
                            <tr key={`${row.cycle_id ?? "fill"}-${index}`} className="border-t border-[var(--border)]">
                              <td className="px-4 py-3 text-[var(--muted)]">{String(row.cycle_id ?? "--")}</td>
                              <td className="px-4 py-3 text-[var(--accent)]">{String(fill?.side ?? "--")}</td>
                              <td className="px-4 py-3 text-[var(--muted)]">{String(fill?.quantity ?? "--")}</td>
                              <td className="px-4 py-3 text-[var(--muted)]">{String(fill?.price ?? "--")}</td>
                            </tr>
                          );
                        })}
                      </tbody>
                    </table>
                  </div>
                </Panel>
              </div>

              <Panel className="p-5">
                <SectionHeader eyebrow="Events" title="Recent Operator Feed" action={`${overviewData.recent_events.length} rows`} />
                <div className="grid gap-3 xl:grid-cols-3">
                  {overviewData.recent_events.slice(0, 6).map((event, index) => (
                    <div
                      key={`${String(event.event_type ?? "event")}-${index}`}
                      className="border border-[var(--border)] bg-[var(--bg-elevated)] px-4 py-4"
                    >
                      <div className="flex items-center justify-between gap-4">
                        <span className="mono text-[10px] uppercase tracking-[0.26em] text-[var(--accent)]">
                          {String(event.event_type ?? "event")}
                        </span>
                        <span className="mono text-[11px] text-[var(--muted)]">
                          {String(event.cycle_id ?? "--")}
                        </span>
                      </div>
                      <p className="mt-3 text-sm leading-6 text-[var(--text)]">{EventMessage(event)}</p>
                    </div>
                  ))}
                </div>
              </Panel>
            </>
          ) : null}
        </section>
      </div>
    </main>
  );
}
