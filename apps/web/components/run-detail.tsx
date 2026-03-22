"use client";

import Link from "next/link";
import useSWR from "swr";

import { fetchJson, type ArtifactDocumentResponse, type ArtifactListResponse } from "@/lib/perpfut-api";


function DetailPanel({
  children,
  className = "",
}: {
  children: React.ReactNode;
  className?: string;
}) {
  return <section className={`panel ${className}`}>{children}</section>;
}

function DetailHeader({
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

function JsonBlock({ value }: { value: Record<string, unknown> | null | undefined }) {
  return (
    <pre className="overflow-x-auto border border-[var(--border)] bg-[var(--bg-elevated)] p-4 text-xs leading-6 text-[var(--muted)]">
      {JSON.stringify(value ?? {}, null, 2)}
    </pre>
  );
}

function ErrorState({ message }: { message: string }) {
  return (
    <DetailPanel className="p-5">
      <DetailHeader eyebrow="Run Detail" title="Unable to load run artifacts" />
      <div className="border border-[rgba(255,109,123,0.38)] bg-[rgba(255,109,123,0.08)] p-4 text-sm leading-6 text-[var(--danger)]">
        {message}
      </div>
    </DetailPanel>
  );
}

function LoadingState() {
  return (
    <DetailPanel className="p-5">
      <DetailHeader eyebrow="Run Detail" title="Loading run artifacts" />
      <div className="signal-grid grid h-72 place-items-center border border-[var(--border)] text-sm text-[var(--muted)]">
        Polling the local operator API for manifest, state, fills, positions, and events.
      </div>
    </DetailPanel>
  );
}

function asRecord(value: unknown): Record<string, unknown> | null {
  return value !== null && typeof value === "object" && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : null;
}

function extractPositionQuantity(row: Record<string, unknown>): string {
  const position = asRecord(row.position);
  const quantity = position?.quantity;
  return typeof quantity === "number" ? quantity.toFixed(6) : "--";
}

function extractFillValue(row: Record<string, unknown>, field: string): string {
  const fill = asRecord(row.fill);
  const value = fill?.[field];
  return typeof value === "number" ? String(value) : String(value ?? "--");
}

function decisionTone(action: string | null | undefined): "accent" | "warning" | "danger" {
  if (action === "filled") {
    return "accent";
  }
  if (action === "halted") {
    return "danger";
  }
  return "warning";
}

function detailValueClass(tone: "accent" | "warning" | "danger" | "text") {
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
      <div className={`mt-3 text-sm leading-6 ${detailValueClass(tone)}`}>{value}</div>
    </div>
  );
}

function DecisionSnapshot({ stateData }: { stateData: Record<string, unknown> }) {
  const signal = asRecord(stateData.signal);
  const riskDecision = asRecord(stateData.risk_decision);
  const executionSummary = asRecord(stateData.execution_summary);
  const noTradeReason = asRecord(stateData.no_trade_reason);

  if (!executionSummary) {
    return (
      <DetailPanel className="p-5">
        <DetailHeader eyebrow="Decision" title="Latest Decision Snapshot" />
        <div className="border border-[var(--border)] bg-[var(--bg-elevated)] p-5 text-sm leading-6 text-[var(--muted)]">
          No normalized decision summary is available in this checkpoint yet.
        </div>
      </DetailPanel>
    );
  }

  const action = typeof executionSummary.action === "string" ? executionSummary.action : null;
  const summary =
    typeof executionSummary.summary === "string"
      ? executionSummary.summary
      : "No operator summary available.";
  const reasonCode =
    typeof executionSummary.reason_code === "string" ? executionSummary.reason_code : "--";
  const reasonMessage =
    typeof noTradeReason?.message === "string"
      ? noTradeReason.message
      : typeof executionSummary.reason_message === "string"
        ? executionSummary.reason_message
        : "--";

  return (
    <DetailPanel className="p-5">
      <DetailHeader eyebrow="Decision" title="Latest Decision Snapshot" action={String(stateData.cycle_id ?? "--")} />
      <div className="border border-[var(--border)] bg-[var(--bg-elevated)] p-4">
        <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
          <div>
            <div className="text-base font-medium text-[var(--text)]">{summary}</div>
            <p className="mt-2 text-sm leading-6 text-[var(--muted)]">{reasonMessage}</p>
          </div>
          <span
            className={`mono inline-flex items-center border px-3 py-2 text-[10px] uppercase tracking-[0.24em] ${detailValueClass(decisionTone(action))} ${
              action === "filled"
                ? "border-[rgba(143,214,255,0.36)] bg-[rgba(143,214,255,0.09)]"
                : action === "halted"
                  ? "border-[rgba(255,109,123,0.36)] bg-[rgba(255,109,123,0.08)]"
                  : "border-[rgba(241,187,103,0.34)] bg-[rgba(241,187,103,0.08)]"
            }`}
          >
            {action ?? "unknown"}
          </span>
        </div>
      </div>

      <div className="mt-4 grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        <DetailMetric label="Reason Code" value={reasonCode} tone={decisionTone(action)} />
        <DetailMetric
          label="Target After Risk"
          value={
            typeof riskDecision?.target_after_risk === "number"
              ? riskDecision.target_after_risk.toFixed(4)
              : typeof signal?.target_position === "number"
                ? signal.target_position.toFixed(4)
                : "--"
          }
          tone="accent"
        />
        <DetailMetric
          label="Current Position"
          value={
            typeof riskDecision?.current_position === "number"
              ? riskDecision.current_position.toFixed(4)
              : "--"
          }
        />
        <DetailMetric
          label="Delta Notional"
          value={
            typeof riskDecision?.delta_notional_usdc === "number"
              ? String(riskDecision.delta_notional_usdc.toFixed(2))
              : "--"
          }
        />
      </div>
    </DetailPanel>
  );
}

export function RunDetail({ runId }: { runId: string }) {
  const manifest = useSWR<ArtifactDocumentResponse>(
    `/runs/${runId}/manifest`,
    (path) => fetchJson(path),
    { refreshInterval: 2_000 }
  );
  const state = useSWR<ArtifactDocumentResponse>(
    `/runs/${runId}/state`,
    (path) => fetchJson(path),
    { refreshInterval: 2_000 }
  );
  const fills = useSWR<ArtifactListResponse>(
    `/runs/${runId}/fills?limit=50`,
    (path) => fetchJson(path),
    { refreshInterval: 2_000 }
  );
  const positions = useSWR<ArtifactListResponse>(
    `/runs/${runId}/positions?limit=50`,
    (path) => fetchJson(path),
    { refreshInterval: 2_000 }
  );
  const events = useSWR<ArtifactListResponse>(
    `/runs/${runId}/events?limit=50`,
    (path) => fetchJson(path),
    { refreshInterval: 2_000 }
  );

  const error = manifest.error ?? state.error ?? fills.error ?? positions.error ?? events.error;
  const isLoading =
    manifest.isLoading || state.isLoading || fills.isLoading || positions.isLoading || events.isLoading;

  if (error) {
    return (
      <main className="min-h-screen px-4 py-4 text-[var(--text)] sm:px-6 lg:px-8">
        <div className="mx-auto max-w-[1680px]">
          <ErrorState message={error.message} />
        </div>
      </main>
    );
  }

  if (isLoading || !manifest.data || !state.data || !fills.data || !positions.data || !events.data) {
    return (
      <main className="min-h-screen px-4 py-4 text-[var(--text)] sm:px-6 lg:px-8">
        <div className="mx-auto max-w-[1680px]">
          <LoadingState />
        </div>
      </main>
    );
  }

  const manifestData = manifest.data.data;
  const stateData = state.data.data;

  return (
    <main className="min-h-screen px-4 py-4 text-[var(--text)] sm:px-6 lg:px-8">
      <div className="mx-auto max-w-[1680px] space-y-4">
        <DetailPanel className="panel-strong p-5">
          <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
            <div>
              <Link href="/" className="mono text-[10px] uppercase tracking-[0.34em] text-[var(--accent)]">
                Back To Overview
              </Link>
              <h1 className="mt-3 text-3xl font-semibold tracking-tight">Run Detail: {runId}</h1>
              <p className="mt-3 max-w-3xl text-sm leading-6 text-[var(--muted)]">
                Read-only inspection of manifest, latest state, fills, position snapshots, and raw
                operator events for a single artifact run.
              </p>
            </div>
            <div className="grid gap-2 text-xs uppercase tracking-[0.22em] text-[var(--muted)] sm:grid-cols-3">
              <div className="border border-[var(--border)] px-3 py-3">
                <div className="mono text-[10px] text-[var(--accent)]">Mode</div>
                <div className="mt-2 text-sm text-[var(--text)]">{String(manifestData.mode ?? "--")}</div>
              </div>
              <div className="border border-[var(--border)] px-3 py-3">
                <div className="mono text-[10px] text-[var(--accent)]">Product</div>
                <div className="mt-2 text-sm text-[var(--text)]">{String(manifestData.product_id ?? "--")}</div>
              </div>
              <div className="border border-[var(--border)] px-3 py-3">
                <div className="mono text-[10px] text-[var(--accent)]">Events</div>
                <div className="mt-2 text-sm text-[var(--text)]">{events.data.count}</div>
              </div>
            </div>
          </div>
        </DetailPanel>

        <div className="grid gap-4 xl:grid-cols-[1.05fr_0.95fr]">
          <DetailPanel className="p-5">
            <DetailHeader eyebrow="Manifest" title="Run Metadata" />
            <JsonBlock value={manifestData} />
          </DetailPanel>

          <DetailPanel className="p-5">
            <DetailHeader eyebrow="State" title="Latest Checkpoint" />
            <JsonBlock value={stateData} />
          </DetailPanel>
        </div>

        <DecisionSnapshot stateData={stateData} />

        <div className="grid gap-4 xl:grid-cols-[1.1fr_0.9fr]">
          <DetailPanel className="p-5">
            <DetailHeader eyebrow="Fills" title="Recent Fill Tape" action={`${fills.data.count} rows`} />
            <div className="overflow-hidden border border-[var(--border)]">
              <table className="w-full border-collapse text-left text-sm">
                <thead className="bg-[rgba(84,191,255,0.06)] text-[var(--muted)]">
                  <tr>
                    {["Cycle", "Side", "Quantity", "Price"].map((cell) => (
                      <th key={cell} className="px-4 py-3 font-medium">
                        {cell}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody className="mono">
                  {fills.data.items.map((row, index) => (
                    <tr key={`${String(row.cycle_id ?? "fill")}-${index}`} className="border-t border-[var(--border)]">
                      <td className="px-4 py-3 text-[var(--muted)]">{String(row.cycle_id ?? "--")}</td>
                      <td className="px-4 py-3 text-[var(--accent)]">{extractFillValue(row, "side")}</td>
                      <td className="px-4 py-3 text-[var(--muted)]">{extractFillValue(row, "quantity")}</td>
                      <td className="px-4 py-3 text-[var(--muted)]">{extractFillValue(row, "price")}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </DetailPanel>

          <DetailPanel className="p-5">
            <DetailHeader eyebrow="Positions" title="Snapshot Timeline" action={`${positions.data.count} rows`} />
            <div className="overflow-hidden border border-[var(--border)]">
              <table className="w-full border-collapse text-left text-sm">
                <thead className="bg-[rgba(84,191,255,0.06)] text-[var(--muted)]">
                  <tr>
                    {["Cycle", "Quantity", "Payload"].map((cell) => (
                      <th key={cell} className="px-4 py-3 font-medium">
                        {cell}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody className="mono">
                  {positions.data.items.map((row, index) => (
                    <tr key={`${String(row.cycle_id ?? "position")}-${index}`} className="border-t border-[var(--border)]">
                      <td className="px-4 py-3 text-[var(--muted)]">{String(row.cycle_id ?? "--")}</td>
                      <td className="px-4 py-3 text-[var(--accent)]">{extractPositionQuantity(row)}</td>
                      <td className="px-4 py-3 text-[var(--muted)]">
                        <span className="line-clamp-1">{JSON.stringify(row.position)}</span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </DetailPanel>
        </div>

        <DetailPanel className="p-5">
          <DetailHeader eyebrow="Events" title="Operator Event Stream" action={`${events.data.count} rows`} />
          <div className="grid gap-3 xl:grid-cols-3">
            {events.data.items.map((event, index) => (
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
                <p className="mt-3 text-sm leading-6 text-[var(--text)]">
                  {String(
                    asRecord(event.execution_summary)?.summary ??
                      asRecord(event.no_trade_reason)?.message ??
                      event.reason ??
                      "artifact event"
                  )}
                </p>
                <pre className="mt-3 overflow-x-auto text-xs leading-6 text-[var(--muted)]">
                  {JSON.stringify(event, null, 2)}
                </pre>
              </div>
            ))}
          </div>
        </DetailPanel>
      </div>
    </main>
  );
}
