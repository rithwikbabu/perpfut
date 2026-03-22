import type { DashboardOverviewResponse } from "@/lib/perpfut-api";


type PositionState = {
  quantity?: number;
  mark_price?: number;
  entry_price?: number | null;
  collateral_usdc?: number;
  realized_pnl_usdc?: number;
};

export type EquityPoint = {
  label: string;
  equity: number;
  realizedPnl: number;
};

export type PositionPoint = {
  label: string;
  target: number;
  current: number;
};

export type DashboardMetrics = {
  equityUsd: number | null;
  realizedPnlUsd: number | null;
  unrealizedPnlUsd: number | null;
  quantity: number | null;
  targetPosition: number | null;
  lastSignalRaw: number | null;
  fillCount: number;
  eventCount: number;
  equitySeries: EquityPoint[];
  positionSeries: PositionPoint[];
};

const DEFAULT_MAX_ABS_NOTIONAL = 20_000;

export function buildDashboardMetrics(overview: DashboardOverviewResponse): DashboardMetrics {
  const cycleEvents = overview.recent_events
    .filter((event) => event.event_type === "cycle")
    .slice()
    .reverse();

  let inferredMaxAbsNotional = DEFAULT_MAX_ABS_NOTIONAL;
  let lastCurrentPosition = 0;

  const equitySeries: EquityPoint[] = [];
  const positionSeries: PositionPoint[] = [];

  for (const event of cycleEvents) {
    const signal = asRecord(event.signal);
    const orderIntent = asRecord(event.order_intent);
    const position = asRecord(event.position);

    const target = asNumber(signal?.target_position) ?? asNumber(event.target_position) ?? 0;
    const rawValue = asNumber(signal?.raw_value);
    const currentNotional = asNumber(orderIntent?.current_notional_usdc);
    const targetNotional = asNumber(orderIntent?.target_notional_usdc);

    if (targetNotional !== null && target !== 0) {
      inferredMaxAbsNotional = Math.max(Math.abs(targetNotional / target), 1);
    }

    if (currentNotional !== null) {
      lastCurrentPosition = currentNotional / inferredMaxAbsNotional;
    }

    const positionState = asPositionState(position);
    const realizedPnl = positionState.realized_pnl_usdc ?? 0;
    const unrealizedPnl = computeUnrealizedPnl(positionState);
    const equity = (positionState.collateral_usdc ?? 0) + realizedPnl + unrealizedPnl;
    const label = String(event.cycle_id ?? event.timestamp ?? event.event_type ?? positionSeries.length + 1);

    equitySeries.push({
      label,
      equity,
      realizedPnl,
    });
    positionSeries.push({
      label,
      target,
      current: lastCurrentPosition,
    });

    if (rawValue !== null) {
      // no-op: computed again from last cycle below
    }
  }

  const latestCycle = cycleEvents.at(-1);
  const latestSignal = asRecord(latestCycle?.signal);
  const latestPosition = asPositionState(asRecord(latestCycle?.position));
  const realizedPnlUsd = latestPosition.realized_pnl_usdc ?? null;
  const unrealizedPnlUsd = computeUnrealizedPnl(latestPosition);
  const equityUsd =
    latestPosition.collateral_usdc !== undefined
      ? (latestPosition.collateral_usdc ?? 0) + (realizedPnlUsd ?? 0) + unrealizedPnlUsd
      : null;

  return {
    equityUsd,
    realizedPnlUsd,
    unrealizedPnlUsd,
    quantity: latestPosition.quantity ?? null,
    targetPosition: asNumber(latestSignal?.target_position),
    lastSignalRaw: asNumber(latestSignal?.raw_value),
    fillCount: overview.recent_fills.length,
    eventCount: overview.recent_events.length,
    equitySeries,
    positionSeries,
  };
}

function asRecord(value: unknown): Record<string, unknown> | null {
  return value !== null && typeof value === "object" && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : null;
}

function asNumber(value: unknown): number | null {
  return typeof value === "number" && Number.isFinite(value) ? value : null;
}

function asPositionState(record: Record<string, unknown> | null): PositionState {
  return {
    quantity: asOptionalNumber(record?.quantity),
    mark_price: asOptionalNumber(record?.mark_price),
    entry_price: asOptionalNumber(record?.entry_price),
    collateral_usdc: asOptionalNumber(record?.collateral_usdc),
    realized_pnl_usdc: asOptionalNumber(record?.realized_pnl_usdc),
  };
}

function computeUnrealizedPnl(state: PositionState): number {
  if (
    state.quantity === undefined ||
    state.entry_price === undefined ||
    state.entry_price === null ||
    state.mark_price === undefined
  ) {
    return 0;
  }
  return (state.mark_price - state.entry_price) * state.quantity;
}

function asOptionalNumber(value: unknown): number | undefined {
  return asNumber(value) ?? undefined;
}

export function formatMoney(value: number | null): string {
  if (value === null) {
    return "--";
  }
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
    maximumFractionDigits: 0,
  }).format(value);
}

export function formatSigned(value: number | null, digits = 2): string {
  if (value === null) {
    return "--";
  }
  return `${value > 0 ? "+" : ""}${value.toFixed(digits)}`;
}

export function formatTimestamp(value: string | null): string {
  if (!value) {
    return "--";
  }
  const parsed = Date.parse(value);
  if (Number.isNaN(parsed)) {
    return value;
  }
  return new Date(parsed).toLocaleString();
}
