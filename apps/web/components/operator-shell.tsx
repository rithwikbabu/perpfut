"use client";

import Link from "next/link";
import { useState } from "react";
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

import {
  buildDashboardMetrics,
  formatMoney,
  formatSigned,
  formatTimestamp,
} from "@/lib/dashboard-metrics";
import {
  ApiError,
  fetchJson,
  startPaperRun,
  stopPaperRun,
  type DashboardOverviewResponse,
  type PaperRunRequest,
  type PaperRunStatusResponse,
  type RunsListResponse,
} from "@/lib/perpfut-api";


const DEFAULT_PAPER_FORM = {
  productId: "BTC-PERP-INTX",
  iterations: "1440",
  intervalSeconds: "60",
  startingCollateralUsdc: "10000",
};

type ControlFeedback = {
  tone: "success" | "danger" | "warning";
  message: string;
};

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

function EmptyPanel({ activeRun }: { activeRun: PaperRunStatusResponse | undefined }) {
  return (
    <Panel className="p-5">
      <SectionHeader eyebrow="Runs" title="No paper artifacts yet" />
      <div className="border border-[var(--border)] bg-[var(--bg-elevated)] p-5 text-sm leading-6 text-[var(--muted)]">
        {activeRun?.active
          ? "A paper process is active. The dashboard will populate once the first run artifacts are written."
          : "Use the paper control panel to start the first run. The dashboard will populate from the artifact history under runs/."}
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

function ControlBanner({ feedback }: { feedback: ControlFeedback }) {
  const classes =
    feedback.tone === "success"
      ? "border-[rgba(155,246,207,0.3)] bg-[rgba(155,246,207,0.08)] text-[var(--success)]"
      : feedback.tone === "warning"
        ? "border-[rgba(241,187,103,0.32)] bg-[rgba(241,187,103,0.08)] text-[var(--warning)]"
        : "border-[rgba(255,109,123,0.3)] bg-[rgba(255,109,123,0.08)] text-[var(--danger)]";

  return (
    <div role={feedback.tone === "danger" ? "alert" : "status"} className={`border px-4 py-3 text-sm ${classes}`}>
      {feedback.message}
    </div>
  );
}

function ControlField({
  label,
  name,
  value,
  onChange,
  disabled,
  inputMode = "text",
}: {
  label: string;
  name: string;
  value: string;
  onChange: (name: string, value: string) => void;
  disabled: boolean;
  inputMode?: React.HTMLAttributes<HTMLInputElement>["inputMode"];
}) {
  return (
    <label className="block">
      <span className="mb-2 block text-[11px] uppercase tracking-[0.22em] text-[var(--muted)]">{label}</span>
      <input
        aria-label={label}
        value={value}
        inputMode={inputMode}
        disabled={disabled}
        onChange={(event) => onChange(name, event.target.value)}
        className="mono w-full border border-[var(--border)] bg-[var(--bg-elevated)] px-3 py-3 text-sm text-[var(--text)] outline-none transition focus:border-[var(--accent)] disabled:cursor-not-allowed disabled:opacity-60"
      />
    </label>
  );
}

function PaperControlPanel({
  activeRun,
  latestRunId,
  form,
  onFieldChange,
  onStart,
  onStop,
  pendingAction,
  feedback,
}: {
  activeRun: PaperRunStatusResponse | undefined;
  latestRunId: string | null;
  form: typeof DEFAULT_PAPER_FORM;
  onFieldChange: (name: string, value: string) => void;
  onStart: () => Promise<void>;
  onStop: () => Promise<void>;
  pendingAction: "start" | "stop" | null;
  feedback: ControlFeedback | null;
}) {
  const isActive = activeRun?.active ?? false;

  return (
    <Panel className="p-5">
      <SectionHeader
        eyebrow="Paper Control"
        title="Start or stop the local paper process"
        action={isActive ? "ACTIVE PROCESS" : "IDLE"}
      />

      <div className="grid gap-4 xl:grid-cols-[1.15fr_0.85fr]">
        <form
          className="space-y-4"
          onSubmit={(event) => {
            event.preventDefault();
            void onStart();
          }}
        >
          <div className="grid gap-4 md:grid-cols-2">
            <ControlField
              label="Product ID"
              name="productId"
              value={form.productId}
              onChange={onFieldChange}
              disabled={isActive || pendingAction !== null}
            />
            <ControlField
              label="Iterations"
              name="iterations"
              value={form.iterations}
              onChange={onFieldChange}
              disabled={isActive || pendingAction !== null}
              inputMode="numeric"
            />
            <ControlField
              label="Interval Seconds"
              name="intervalSeconds"
              value={form.intervalSeconds}
              onChange={onFieldChange}
              disabled={isActive || pendingAction !== null}
              inputMode="numeric"
            />
            <ControlField
              label="Starting Collateral USDC"
              name="startingCollateralUsdc"
              value={form.startingCollateralUsdc}
              onChange={onFieldChange}
              disabled={isActive || pendingAction !== null}
              inputMode="decimal"
            />
          </div>

          <div className="flex flex-wrap gap-3">
            <button
              type="submit"
              disabled={isActive || pendingAction !== null}
              className="mono border border-[var(--accent)] bg-[rgba(84,191,255,0.12)] px-4 py-3 text-sm uppercase tracking-[0.24em] text-[var(--text)] transition hover:bg-[rgba(84,191,255,0.18)] disabled:cursor-not-allowed disabled:border-[var(--border)] disabled:bg-[rgba(255,255,255,0.03)] disabled:text-[var(--muted)]"
            >
              {pendingAction === "start" ? "Starting..." : "Start Paper Run"}
            </button>
            <button
              type="button"
              onClick={() => void onStop()}
              disabled={!isActive || pendingAction !== null}
              className="mono border border-[rgba(255,109,123,0.34)] bg-[rgba(255,109,123,0.08)] px-4 py-3 text-sm uppercase tracking-[0.24em] text-[var(--text)] transition hover:bg-[rgba(255,109,123,0.14)] disabled:cursor-not-allowed disabled:border-[var(--border)] disabled:bg-[rgba(255,255,255,0.03)] disabled:text-[var(--muted)]"
            >
              {pendingAction === "stop" ? "Stopping..." : "Stop Active Run"}
            </button>
          </div>
        </form>

        <div className="border border-[var(--border)] bg-[var(--bg-elevated)] p-4">
          <div className="mono text-[10px] uppercase tracking-[0.28em] text-[var(--accent)]">
            Active Paper Status
          </div>
          <div className="mt-4 flex items-center gap-3">
            <span
              className={`mono inline-flex items-center border px-3 py-2 text-[10px] uppercase tracking-[0.24em] ${
                isActive
                  ? "border-[rgba(155,246,207,0.32)] bg-[rgba(155,246,207,0.08)] text-[var(--success)]"
                  : "border-[var(--border)] bg-[rgba(255,255,255,0.03)] text-[var(--muted)]"
              }`}
            >
              {isActive ? "ACTIVE" : "IDLE"}
            </span>
            <span className="text-sm text-[var(--muted)]">
              {isActive ? `PID ${activeRun?.pid ?? "--"}` : "No process registered"}
            </span>
          </div>

          <dl className="mt-4 space-y-3 text-sm">
            <div className="flex items-center justify-between gap-4">
              <dt className="text-[var(--muted)]">Product</dt>
              <dd className="mono text-[var(--text)]">{activeRun?.product_id ?? form.productId}</dd>
            </div>
            <div className="flex items-center justify-between gap-4">
              <dt className="text-[var(--muted)]">Started</dt>
              <dd className="text-[var(--text)]">{formatTimestamp(activeRun?.started_at ?? null)}</dd>
            </div>
            <div className="flex items-center justify-between gap-4">
              <dt className="text-[var(--muted)]">Run Artifacts</dt>
              <dd className="mono text-[var(--text)]">{latestRunId ?? "--"}</dd>
            </div>
            <div className="flex items-center justify-between gap-4">
              <dt className="text-[var(--muted)]">Log Path</dt>
              <dd className="mono text-[var(--text)]">{activeRun?.log_path ?? "--"}</dd>
            </div>
          </dl>
        </div>
      </div>

      {feedback ? <div className="mt-4"><ControlBanner feedback={feedback} /></div> : null}
    </Panel>
  );
}

function asRecord(value: unknown): Record<string, unknown> | null {
  return value !== null && typeof value === "object" && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : null;
}

function parsePaperRunRequest(form: typeof DEFAULT_PAPER_FORM): {
  request: PaperRunRequest | null;
  error: string | null;
} {
  const productId = form.productId.trim();
  const iterations = Number.parseInt(form.iterations, 10);
  const intervalSeconds = Number.parseInt(form.intervalSeconds, 10);
  const startingCollateralUsdc = Number.parseFloat(form.startingCollateralUsdc);

  if (!productId) {
    return { request: null, error: "Product ID is required." };
  }
  if (!Number.isInteger(iterations) || iterations <= 0) {
    return { request: null, error: "Iterations must be a positive integer." };
  }
  if (!Number.isInteger(intervalSeconds) || intervalSeconds < 0) {
    return { request: null, error: "Interval Seconds must be an integer greater than or equal to zero." };
  }
  if (!Number.isFinite(startingCollateralUsdc) || startingCollateralUsdc <= 0) {
    return { request: null, error: "Starting Collateral USDC must be greater than zero." };
  }

  return {
    request: {
      productId,
      iterations,
      intervalSeconds,
      startingCollateralUsdc,
    },
    error: null,
  };
}

function formatControlError(error: unknown): ControlFeedback {
  if (error instanceof ApiError) {
    if (error.status === 409) {
      return {
        tone: "warning",
        message: "A paper run is already active. The control panel has refreshed the latest status.",
      };
    }
    return {
      tone: "danger",
      message: error.message,
    };
  }
  return {
    tone: "danger",
    message: error instanceof Error ? error.message : "Unknown control-plane error.",
  };
}

export function OperatorShell() {
  const [form, setForm] = useState(DEFAULT_PAPER_FORM);
  const [pendingAction, setPendingAction] = useState<"start" | "stop" | null>(null);
  const [feedback, setFeedback] = useState<ControlFeedback | null>(null);

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
  const activeRun = useSWR<PaperRunStatusResponse>(
    "/paper-runs/active",
    (path) => fetchJson(path),
    { refreshInterval: 2_000 }
  );

  const overviewData = overview.data;
  const metrics = overviewData ? buildDashboardMetrics(overviewData) : null;
  const latestRun = overviewData?.latest_run;
  const currentProductId = latestRun?.product_id ?? activeRun.data?.product_id ?? form.productId;
  const isLoading = overview.isLoading || runs.isLoading || activeRun.isLoading;
  const error = overview.error ?? runs.error ?? activeRun.error;

  function handleFieldChange(name: string, value: string) {
    setForm((current) => ({ ...current, [name]: value }));
  }

  async function refreshOperatorViews(nextActive?: PaperRunStatusResponse) {
    await Promise.all([
      overview.mutate(),
      runs.mutate(),
      nextActive
        ? activeRun.mutate(nextActive, { revalidate: false })
        : activeRun.mutate(),
    ]);
  }

  async function handleStart() {
    const parsed = parsePaperRunRequest(form);
    if (!parsed.request) {
      setFeedback({ tone: "danger", message: parsed.error ?? "Invalid request." });
      return;
    }

    setPendingAction("start");
    setFeedback(null);

    try {
      const status = await startPaperRun(parsed.request);
      setFeedback({
        tone: "success",
        message: `Paper run started for ${status.product_id ?? parsed.request.productId}.`,
      });
      await refreshOperatorViews(status);
    } catch (error) {
      setFeedback(formatControlError(error));
      await refreshOperatorViews();
    } finally {
      setPendingAction(null);
    }
  }

  async function handleStop() {
    setPendingAction("stop");
    setFeedback(null);

    try {
      const status = await stopPaperRun();
      setFeedback({
        tone: "success",
        message: status.active
          ? "Paper run remains active."
          : "Paper run stop signal completed.",
      });
      await refreshOperatorViews(status);
    } catch (error) {
      setFeedback(formatControlError(error));
      await refreshOperatorViews();
    } finally {
      setPendingAction(null);
    }
  }

  return (
    <main className="min-h-screen px-4 py-4 text-[var(--text)] sm:px-6 lg:px-8">
      <div className="mx-auto grid max-w-[1680px] gap-4 lg:grid-cols-[260px_minmax(0,1fr)]">
        <aside className="panel flex min-h-[calc(100vh-2rem)] flex-col justify-between p-5">
          <div>
            <div className="mono text-[11px] uppercase tracking-[0.34em] text-[var(--accent)]">perpfut</div>
            <div className="mt-3 text-2xl font-semibold tracking-tight">Operator Console</div>
            <p className="mt-3 max-w-xs text-sm leading-6 text-[var(--muted)]">
              Local-first monitoring for paper execution, artifact inspection, and operator control.
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

          <div className="space-y-4">
            <div className="border border-[var(--border)] bg-[var(--bg-elevated)] p-4">
              <div className="mono text-[10px] uppercase tracking-[0.28em] text-[var(--warning)]">
                Control Plane
              </div>
              <div className="mt-3 text-sm text-[var(--text)]">
                {activeRun.data?.active ? "Paper process active" : "Paper process idle"}
              </div>
              <p className="mt-2 text-sm leading-6 text-[var(--muted)]">
                {activeRun.data?.active
                  ? `${activeRun.data.product_id ?? "Unknown product"} · PID ${activeRun.data.pid ?? "--"}`
                  : "No active paper process is registered."}
              </p>
            </div>

            <div className="border border-[var(--border)] bg-[var(--bg-elevated)] p-4">
              <div className="mono text-[10px] uppercase tracking-[0.28em] text-[var(--warning)]">
                Latest Run
              </div>
              {latestRun ? (
                <Link
                  href={`/runs/${latestRun.run_id}`}
                  className="mt-3 block text-sm text-[var(--text)] underline decoration-[var(--border)] underline-offset-4"
                >
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
                latest-run telemetry, recent fills, cycle-level positioning, and local paper-run
                controls.
              </p>
            </div>
            <div className="grid gap-2 text-xs uppercase tracking-[0.22em] text-[var(--muted)] sm:grid-cols-3">
              <div className="border border-[var(--border)] px-3 py-3">
                <div className="mono text-[10px] text-[var(--accent)]">Mode</div>
                <div className="mt-2 text-sm text-[var(--text)]">Paper</div>
              </div>
              <div className="border border-[var(--border)] px-3 py-3">
                <div className="mono text-[10px] text-[var(--accent)]">Product</div>
                <div className="mt-2 text-sm text-[var(--text)]">{currentProductId}</div>
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

          {!error && !isLoading ? (
            <PaperControlPanel
              activeRun={activeRun.data}
              latestRunId={latestRun?.run_id ?? null}
              form={form}
              onFieldChange={handleFieldChange}
              onStart={handleStart}
              onStop={handleStop}
              pendingAction={pendingAction}
              feedback={feedback}
            />
          ) : null}

          {!error && !isLoading && !latestRun ? <EmptyPanel activeRun={activeRun.data} /> : null}

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
