import { BacktestRunShell } from "@/components/backtest-run-shell";


export default async function BacktestRunPage({
  params,
}: {
  params: Promise<{ runId: string }>;
}) {
  const { runId } = await params;
  return <BacktestRunShell runId={runId} />;
}
