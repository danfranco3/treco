"use client";

import { Card } from "@/components/ui/Card";
import type { MetricRow } from "@/lib/types";

function latestByMetric(rows: MetricRow[]): Record<string, MetricRow> {
  const out: Record<string, MetricRow> = {};
  for (const row of rows) out[row.metric] = row; // rows are time-ordered; last wins
  return out;
}

function fmtValue(row: MetricRow): string {
  switch (row.unit) {
    case "usd":
      return `$${row.value.toFixed(4)}`;
    case "ms":
      return row.value >= 60_000
        ? `${(row.value / 60_000).toFixed(1)}m`
        : `${(row.value / 1000).toFixed(1)}s`;
    case "ratio":
      return `${(row.value * 100).toFixed(0)}%`;
    default:
      return row.value.toLocaleString();
  }
}

function RatioBar({ label, row, warnAt }: { label: string; row: MetricRow; warnAt: number }) {
  const pct = Math.min(row.value * 100, 100);
  const warn = row.value >= warnAt;
  return (
    <div className="flex flex-col gap-1">
      <div className="flex items-center justify-between text-xs">
        <span className="text-text-muted">{label}</span>
        <span className={warn ? "text-red-brand font-semibold" : "text-text-primary"}>
          {fmtValue(row)}
        </span>
      </div>
      <div className="h-1.5 rounded-full bg-[var(--surface-2)] overflow-hidden">
        <div
          className={`h-full rounded-full transition-all ${warn ? "bg-red-brand" : "bg-green-brand"}`}
          style={{ width: `${pct}%` }}
        />
      </div>
    </div>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex flex-col">
      <span className="text-[10px] uppercase tracking-wide text-text-muted font-semibold">{label}</span>
      <span className="text-sm font-mono text-text-primary">{value}</span>
    </div>
  );
}

const STAT_METRICS: [string, string][] = [
  ["tokens_in_per_ticket", "Tokens in"],
  ["tokens_out_per_ticket", "Tokens out"],
  ["cost_usd_per_ticket", "Cost"],
  ["time_to_completion", "Duration"],
  ["interventions_per_ticket", "Interventions"],
  ["loop_count_per_ticket", "Loops"],
];

export function MetricsPanel({ metrics }: { metrics: MetricRow[] }) {
  if (metrics.length === 0) return null;
  const latest = latestByMetric(metrics);

  return (
    <Card className="flex flex-col gap-3">
      <h3 className="text-xs font-semibold text-text-muted uppercase tracking-wider">
        Telemetry
      </h3>
      <div className="grid grid-cols-3 gap-3">
        {STAT_METRICS.map(([key, label]) =>
          latest[key] ? <Stat key={key} label={label} value={fmtValue(latest[key])} /> : null
        )}
      </div>
      <div className="flex flex-col gap-2">
        {latest.loop_utilization_ratio && (
          <RatioBar label="Loop budget (30-turn cap)" row={latest.loop_utilization_ratio} warnAt={1} />
        )}
        {latest.context_saturation_ratio && (
          <RatioBar label="Context saturation" row={latest.context_saturation_ratio} warnAt={0.8} />
        )}
      </div>
    </Card>
  );
}
