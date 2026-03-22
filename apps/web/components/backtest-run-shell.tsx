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

import { ConsoleNav } from "@/components/console-nav";
import {
  buildAnalysisMetrics,
  formatDateRange,
  formatCount,
  formatMoney,
  formatPercent,
  formatSharpe,
  formatSigned,
  formatSignedPercent,
  formatTimestamp,
} from "@/lib/dashboard-metrics";
import {
  fetchJson,
  type ArtifactListResponse,
  type BacktestRunDetailResponse,
} from "@/lib/perpfut-api";


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

function LoadingState() {
  return (
    <ShellPanel className="p-5">
      <ShellHeader eyebrow="Backtest Detail" title="Loading backtest artifacts" />
      <div className="signal-grid grid h-72 place-items-center border border-[var(--border)] text-sm text-[var(--muted)]">
        Polling the local backtest API for detail, events, fills, and positions.
      </div>
    </ShellPanel>
  );
}

function ErrorState({ message }: { message: string }) {
  return (
    <ShellPanel className="p-5">
      <ShellHeader eyebrow="Backtest Detail" title="Unable to load backtest artifacts" />
      <div className="border border-[rgba(255,109,123,0.38)] bg-[rgba(255,109,123,0.08)] p-4 text-sm leading-6 text-[var(--danger)]">
        {message}
      </div>
    </ShellPanel>
  );
}

function asRecord(value: unknown): Record<string, unknown> | null {
  return value !== null && typeof value === "object" && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : null;
}

function metricTone(value: number | null | undefined): "accent" | "warning" | "text" {
  if (typeof value !== "number") {
    return "text";
  }
  if (value > 0) {
    return "accent";
  }
  if (value < 0) {
    return "warning";
  }
  return "text";
}

function valueClass(tone: "accent" | "warning" | "danger" | "text") {
  if (tone === "accent") {
    return "text-[var(--accent)]";
  }
  if (tone === "warning") {
    return "text-[var(--warning)]";
  }
  if (tone === "danger") {
    return "text-[var(--danger)]";
  }
  return "text-[var(--text)]";
}

function DetailMetric({
  label,
  value,
  tone = "text",
}: {
  label: string;
  value: string;
  tone?: "accent" | "warning" | "danger" | "text";
}) {
  return (
    <div className="border border-[var(--border)] bg-[var(--bg-elevated)] px-4 py-4">
      <div className="mono text-[10px] uppercase tracking-[0.24em] text-[var(--muted)]">{label}</div>
      <div className={`mt-3 text-sm leading-6 ${valueClass(tone)}`}>{value}</div>
    </div>
  );
}

function EmptyBlock({ message }: { message: string }) {
  return (
    <div className="border border-[var(--border)] bg-[var(--bg-elevated)] p-5 text-sm leading-6 text-[var(--muted)]">
      {message}
    </div>
  );
}

function PendingBlock({ message }: { message: string }) {
  return (
    <div className="signal-grid grid min-h-48 place-items-center border border-[var(--border)] bg-[var(--bg-elevated)] p-5 text-sm text-[var(--muted)]">
      {message}
    </div>
  );
}

function PerformancePanel({ detail }: { detail: BacktestRunDetailResponse }) {
  const metrics = buildAnalysisMetrics(detail.analysis);

  return (
    <>
      <ShellPanel className="p-5">
        <ShellHeader eyebrow="Performance" title="Canonical backtest analysis" action={`${formatCount(metrics.cycleCount)} cycles`} />
        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
          <DetailMetric label="Total Return" value={formatSignedPercent(metrics.totalReturnPct)} tone="accent" />
          <DetailMetric
            label="Total P&L"
            value={formatMoney(metrics.totalPnlUsd)}
            tone={metricTone(metrics.totalPnlUsd)}
          />
          <DetailMetric label="Max Drawdown" value={formatPercent(metrics.maxDrawdownPct)} tone="warning" />
          <DetailMetric label="Sharpe" value={formatSharpe(detail.analysis.sharpe_ratio)} />
          <DetailMetric
            label="Date Range"
            value={formatDateRange(detail.analysis.date_range_start, detail.analysis.date_range_end)}
          />
          <DetailMetric label="Turnover" value={formatMoney(metrics.turnoverUsd)} />
          <DetailMetric label="Fills" value={formatCount(metrics.fillCount)} />
        </div>
      </ShellPanel>

      <div className="grid gap-4 xl:grid-cols-3">
        <ShellPanel className="p-5">
          <ShellHeader eyebrow="Chart" title="Equity Curve" />
          {metrics.equitySeries.length > 0 ? (
            <div className="h-64">
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={metrics.equitySeries}>
                  <CartesianGrid stroke="rgba(143,214,255,0.08)" vertical={false} />
                  <XAxis dataKey="label" stroke="rgba(144,164,191,0.72)" tickLine={false} axisLine={false} />
                  <YAxis stroke="rgba(144,164,191,0.72)" tickLine={false} axisLine={false} width={48} />
                  <Tooltip
                    cursor={{ stroke: "rgba(143,214,255,0.18)" }}
                    contentStyle={{
                      background: "rgba(10,16,27,0.96)",
                      border: "1px solid rgba(184,211,242,0.24)",
                      color: "#ecf4ff",
                    }}
                  />
                  <Line type="monotone" dataKey="value" stroke="var(--accent)" strokeWidth={2} dot={false} />
                </LineChart>
              </ResponsiveContainer>
            </div>
          ) : (
            <EmptyBlock message="No equity series available for this backtest run." />
          )}
        </ShellPanel>

        <ShellPanel className="p-5">
          <ShellHeader eyebrow="Chart" title="Drawdown Curve" />
          {metrics.drawdownSeries.length > 0 ? (
            <div className="h-64">
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={metrics.drawdownSeries}>
                  <CartesianGrid stroke="rgba(143,214,255,0.08)" vertical={false} />
                  <XAxis dataKey="label" stroke="rgba(144,164,191,0.72)" tickLine={false} axisLine={false} />
                  <YAxis stroke="rgba(144,164,191,0.72)" tickLine={false} axisLine={false} width={48} />
                  <Tooltip
                    cursor={{ stroke: "rgba(241,187,103,0.18)" }}
                    contentStyle={{
                      background: "rgba(10,16,27,0.96)",
                      border: "1px solid rgba(184,211,242,0.24)",
                      color: "#ecf4ff",
                    }}
                  />
                  <Line type="monotone" dataKey="value" stroke="var(--warning)" strokeWidth={2} dot={false} />
                </LineChart>
              </ResponsiveContainer>
            </div>
          ) : (
            <EmptyBlock message="No drawdown series available for this backtest run." />
          )}
        </ShellPanel>

        <ShellPanel className="p-5">
          <ShellHeader eyebrow="Chart" title="Absolute Exposure Timeline" />
          {metrics.exposureSeries.length > 0 ? (
            <div className="h-64">
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={metrics.exposureSeries}>
                  <CartesianGrid stroke="rgba(143,214,255,0.08)" vertical={false} />
                  <XAxis dataKey="label" stroke="rgba(144,164,191,0.72)" tickLine={false} axisLine={false} />
                  <YAxis stroke="rgba(144,164,191,0.72)" tickLine={false} axisLine={false} width={48} />
                  <Tooltip
                    cursor={{ stroke: "rgba(143,214,255,0.18)" }}
                    contentStyle={{
                      background: "rgba(10,16,27,0.96)",
                      border: "1px solid rgba(184,211,242,0.24)",
                      color: "#ecf4ff",
                    }}
                  />
                  <Line type="monotone" dataKey="value" stroke="var(--success)" strokeWidth={2} dot={false} />
                </LineChart>
              </ResponsiveContainer>
            </div>
          ) : (
            <EmptyBlock message="No exposure series available for this backtest run." />
          )}
        </ShellPanel>
      </div>
    </>
  );
}

function PortfolioSnapshot({
  detail,
  positions,
  positionsLoading,
}: {
  detail: BacktestRunDetailResponse;
  positions: ArtifactListResponse | undefined;
  positionsLoading: boolean;
}) {
  const portfolio = asRecord(detail.state.portfolio) ?? asRecord(detail.state.position);
  const latestPositionRow = positions?.items[0] ? asRecord(positions.items[0]) : null;
  const assetPositions = asRecord(latestPositionRow?.asset_positions) ?? asRecord(detail.state.asset_positions);
  const manifest = detail.manifest;

  return (
    <div className="grid gap-4 xl:grid-cols-[0.95fr_1.05fr]">
      <ShellPanel className="p-5">
        <ShellHeader eyebrow="Portfolio" title="Latest portfolio checkpoint" action={String(detail.state.cycle_id ?? "--")} />
        <div className="grid gap-4 md:grid-cols-2">
          <DetailMetric
            label="Ending Equity"
            value={formatMoney(typeof portfolio?.equity_usdc === "number" ? portfolio.equity_usdc : detail.analysis.ending_equity_usdc)}
            tone="accent"
          />
          <DetailMetric
            label="Gross Notional"
            value={formatMoney(typeof portfolio?.gross_notional_usdc === "number" ? portfolio.gross_notional_usdc : null)}
          />
          <DetailMetric
            label="Realized P&L"
            value={formatMoney(typeof portfolio?.realized_pnl_usdc === "number" ? portfolio.realized_pnl_usdc : detail.analysis.realized_pnl_usdc)}
            tone={metricTone(typeof portfolio?.realized_pnl_usdc === "number" ? portfolio.realized_pnl_usdc : detail.analysis.realized_pnl_usdc)}
          />
          <DetailMetric
            label="Unrealized P&L"
            value={formatMoney(typeof portfolio?.unrealized_pnl_usdc === "number" ? portfolio.unrealized_pnl_usdc : detail.analysis.unrealized_pnl_usdc)}
            tone={metricTone(typeof portfolio?.unrealized_pnl_usdc === "number" ? portfolio.unrealized_pnl_usdc : detail.analysis.unrealized_pnl_usdc)}
          />
          <DetailMetric label="Suite" value={String(manifest.suite_id ?? "--")} />
          <DetailMetric label="Dataset" value={String(manifest.dataset_id ?? "--")} />
        </div>
      </ShellPanel>

      <ShellPanel className="p-5">
        <ShellHeader eyebrow="Assets" title="Latest per-asset positions" />
        {positionsLoading && !assetPositions ? (
          <PendingBlock message="Loading the latest per-asset position snapshot." />
        ) : assetPositions ? (
          <div className="overflow-x-auto border border-[var(--border)] bg-[var(--bg-elevated)]">
            <table className="min-w-full text-left text-sm">
              <thead className="border-b border-[var(--border)] text-[var(--muted)]">
                <tr>
                  <th className="px-4 py-3 font-medium">Asset</th>
                  <th className="px-4 py-3 font-medium">Quantity</th>
                  <th className="px-4 py-3 font-medium">Entry</th>
                  <th className="px-4 py-3 font-medium">Mark</th>
                  <th className="px-4 py-3 font-medium">Realized</th>
                </tr>
              </thead>
              <tbody>
                {Object.entries(assetPositions).map(([productId, value]) => {
                  const position = asRecord(value);
                  return (
                    <tr key={productId} className="border-b border-[var(--border)] last:border-b-0">
                      <td className="px-4 py-3 text-[var(--text)]">{productId}</td>
                      <td className="px-4 py-3 text-[var(--text)]">
                        {formatSigned(typeof position?.quantity === "number" ? position.quantity : null, 4)}
                      </td>
                      <td className="px-4 py-3 text-[var(--muted)]">
                        {typeof position?.entry_price === "number" ? position.entry_price.toFixed(2) : "--"}
                      </td>
                      <td className="px-4 py-3 text-[var(--muted)]">
                        {typeof position?.mark_price === "number" ? position.mark_price.toFixed(2) : "--"}
                      </td>
                      <td className="px-4 py-3 text-[var(--text)]">
                        {formatMoney(typeof position?.realized_pnl_usdc === "number" ? position.realized_pnl_usdc : null)}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        ) : (
          <EmptyBlock message="No per-asset position snapshot was written for this backtest run." />
        )}
      </ShellPanel>
    </div>
  );
}

function DecisionPanel({
  events,
  eventsLoading,
}: {
  events: ArtifactListResponse | undefined;
  eventsLoading: boolean;
}) {
  const latestEvent = events?.items[0] ? asRecord(events.items[0]) : null;
  const assetDecisions = asRecord(latestEvent?.asset_decisions);

  return (
    <ShellPanel className="p-5">
      <ShellHeader eyebrow="Decisions" title="Latest asset decision set" action={String(latestEvent?.cycle_id ?? "--")} />
      {eventsLoading ? (
        <PendingBlock message="Loading the latest asset decision set." />
      ) : assetDecisions ? (
        <div className="grid gap-4 xl:grid-cols-2">
          {Object.entries(assetDecisions).map(([productId, value]) => {
            const decision = asRecord(value);
            const signal = asRecord(decision?.signal);
            const risk = asRecord(decision?.risk_decision);
            const execution = asRecord(decision?.execution_summary);
            const noTrade = asRecord(decision?.no_trade_reason);
            return (
              <div key={productId} className="border border-[var(--border)] bg-[var(--bg-elevated)] p-4">
                <div className="flex items-center justify-between gap-4">
                  <div className="text-sm font-medium text-[var(--text)]">{productId}</div>
                  <div className="mono text-[10px] uppercase tracking-[0.24em] text-[var(--muted)]">
                    {String(execution?.action ?? "unknown")}
                  </div>
                </div>
                <p className="mt-3 text-sm leading-6 text-[var(--muted)]">
                  {typeof execution?.summary === "string"
                    ? execution.summary
                    : typeof noTrade?.message === "string"
                      ? noTrade.message
                      : "No execution summary available."}
                </p>
                <div className="mt-4 grid gap-3 md:grid-cols-2">
                  <DetailMetric
                    label="Signal Target"
                    value={formatSigned(typeof signal?.target_position === "number" ? signal.target_position : null, 4)}
                    tone="accent"
                  />
                  <DetailMetric
                    label="Delta Notional"
                    value={formatMoney(typeof risk?.delta_notional_usdc === "number" ? risk.delta_notional_usdc : null)}
                  />
                </div>
              </div>
            );
          })}
        </div>
      ) : (
        <EmptyBlock message="No asset-level decision payload was found in the latest event." />
      )}
    </ShellPanel>
  );
}

function FillPanel({
  fills,
  fillsLoading,
}: {
  fills: ArtifactListResponse | undefined;
  fillsLoading: boolean;
}) {
  return (
    <ShellPanel className="p-5">
      <ShellHeader eyebrow="Fills" title="Recent backtest fill tape" action={`${fills?.count ?? 0} rows`} />
      {fillsLoading ? (
        <PendingBlock message="Loading recent backtest fills." />
      ) : fills && fills.items.length > 0 ? (
        <div className="overflow-x-auto border border-[var(--border)] bg-[var(--bg-elevated)]">
          <table className="min-w-full text-left text-sm">
            <thead className="border-b border-[var(--border)] text-[var(--muted)]">
              <tr>
                <th className="px-4 py-3 font-medium">Cycle</th>
                <th className="px-4 py-3 font-medium">Asset</th>
                <th className="px-4 py-3 font-medium">Side</th>
                <th className="px-4 py-3 font-medium">Quantity</th>
                <th className="px-4 py-3 font-medium">Price</th>
              </tr>
            </thead>
            <tbody>
              {fills.items.map((row) => {
                const item = asRecord(row);
                const fill = asRecord(item?.fill);
                return (
                  <tr key={`${String(item?.cycle_id ?? "--")}-${String(item?.product_id ?? "--")}`} className="border-b border-[var(--border)] last:border-b-0">
                    <td className="px-4 py-3 text-[var(--muted)]">{String(item?.cycle_id ?? "--")}</td>
                    <td className="px-4 py-3 text-[var(--text)]">{String(item?.product_id ?? "--")}</td>
                    <td className="px-4 py-3 text-[var(--text)]">{String(fill?.side ?? "--")}</td>
                    <td className="px-4 py-3 text-[var(--muted)]">
                      {typeof fill?.quantity === "number" ? fill.quantity.toFixed(6) : "--"}
                    </td>
                    <td className="px-4 py-3 text-[var(--muted)]">
                      {typeof fill?.price === "number" ? fill.price.toFixed(2) : "--"}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      ) : (
        <EmptyBlock message="This backtest run has no recorded fills yet." />
      )}
    </ShellPanel>
  );
}

function EventPanel({
  events,
  eventsLoading,
}: {
  events: ArtifactListResponse | undefined;
  eventsLoading: boolean;
}) {
  return (
    <ShellPanel className="p-5">
      <ShellHeader eyebrow="Events" title="Backtest event stream" action={`${events?.count ?? 0} rows`} />
      {eventsLoading ? (
        <PendingBlock message="Loading the backtest event stream." />
      ) : events && events.items.length > 0 ? (
        <div className="overflow-x-auto border border-[var(--border)] bg-[var(--bg-elevated)]">
          <table className="min-w-full text-left text-sm">
            <thead className="border-b border-[var(--border)] text-[var(--muted)]">
              <tr>
                <th className="px-4 py-3 font-medium">Cycle</th>
                <th className="px-4 py-3 font-medium">Action</th>
                <th className="px-4 py-3 font-medium">Reason</th>
                <th className="px-4 py-3 font-medium">Summary</th>
              </tr>
            </thead>
            <tbody>
              {events.items.map((row) => {
                const item = asRecord(row);
                const execution = asRecord(item?.execution_summary);
                const noTrade = asRecord(item?.no_trade_reason);
                return (
                  <tr key={String(item?.cycle_id ?? "--")} className="border-b border-[var(--border)] last:border-b-0">
                    <td className="px-4 py-3 text-[var(--muted)]">{String(item?.cycle_id ?? "--")}</td>
                    <td className="px-4 py-3 text-[var(--text)]">{String(execution?.action ?? "--")}</td>
                    <td className="px-4 py-3 text-[var(--warning)]">
                      {String(execution?.reason_code ?? noTrade?.code ?? "--")}
                    </td>
                    <td className="px-4 py-3 text-[var(--muted)]">
                      {String(execution?.summary ?? noTrade?.message ?? "--")}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      ) : (
        <EmptyBlock message="No event stream is available for this backtest run." />
      )}
    </ShellPanel>
  );
}

export function BacktestRunShell({ runId }: { runId: string }) {
  const detail = useSWR<BacktestRunDetailResponse>(`/backtests/${runId}`, fetchJson, {
    refreshInterval: 2000,
  });
  const events = useSWR<ArtifactListResponse>(`/backtests/${runId}/events?limit=20`, fetchJson, {
    refreshInterval: 2000,
  });
  const fills = useSWR<ArtifactListResponse>(`/backtests/${runId}/fills?limit=20`, fetchJson, {
    refreshInterval: 2000,
  });
  const positions = useSWR<ArtifactListResponse>(`/backtests/${runId}/positions?limit=20`, fetchJson, {
    refreshInterval: 2000,
  });

  const loading = !detail.data && !detail.error;
  const eventsLoading = !events.data && !events.error;
  const fillsLoading = !fills.data && !fills.error;
  const positionsLoading = !positions.data && !positions.error;
  const error = detail.error ?? events.error ?? fills.error ?? positions.error;

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
                {detail.data
                  ? `${String(detail.data.manifest.strategy_id ?? "--")} · ${String(detail.data.manifest.suite_id ?? "--")}`
                  : "Waiting for the backtest detail payload."}
              </p>
            </div>

            <div className="border border-[var(--border)] bg-[var(--bg-elevated)] p-4">
              <div className="mono text-[10px] uppercase tracking-[0.28em] text-[var(--warning)]">
                Analysis Window
              </div>
              <div className="mt-3 text-sm text-[var(--text)]">
                {detail.data
                  ? formatDateRange(detail.data.analysis.date_range_start, detail.data.analysis.date_range_end)
                  : "--"}
              </div>
              <p className="mt-2 text-sm leading-6 text-[var(--muted)]">
                {detail.data
                  ? `${formatSharpe(detail.data.analysis.sharpe_ratio)} Sharpe · ${formatCount(detail.data.analysis.fill_count)} fills · ${formatCount(detail.data.analysis.cycle_count)} cycles`
                  : "No analysis summary loaded yet."}
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
                This page reads the canonical backtest detail payload plus recent artifacts and surfaces
                analysis, per-asset decisions, fills, and portfolio inspection without raw JSON digging.
              </p>
            </div>
            <Link
              href="/backtests"
              className="inline-flex items-center border border-[var(--border)] px-4 py-3 text-xs uppercase tracking-[0.24em] text-[var(--muted)] transition hover:border-[var(--border-strong)] hover:text-[var(--text)]"
            >
              Back to Backtests
            </Link>
          </header>

          {loading ? <LoadingState /> : null}
          {error ? <ErrorState message={error.message} /> : null}

          {detail.data && !error ? (
            <>
              <PerformancePanel detail={detail.data} />
              <PortfolioSnapshot detail={detail.data} positions={positions.data} positionsLoading={positionsLoading} />
              <DecisionPanel events={events.data} eventsLoading={eventsLoading} />
              <div className="grid gap-4 xl:grid-cols-[0.95fr_1.05fr]">
                <FillPanel fills={fills.data} fillsLoading={fillsLoading} />
                <EventPanel events={events.data} eventsLoading={eventsLoading} />
              </div>
            </>
          ) : null}
        </section>
      </div>
    </main>
  );
}
