"use client";

import { useMemo } from "react";
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer } from "recharts";
import type { AgentEvent, CostSummary } from "@/lib/types";
import { estimateCost, formatCost, formatTokens } from "@/lib/cost";
import { Card } from "@/components/ui/Card";

interface CostPanelProps {
  cost: CostSummary;
  events: AgentEvent[];
}

export function CostPanel({ cost, events }: CostPanelProps) {
  const totalCost = estimateCost(cost.total_tokens_in, cost.total_tokens_out, null);

  const byModel = useMemo(() => {
    const map: Record<string, { in: number; out: number }> = {};
    for (const ev of events) {
      const key = ev.model ?? "unknown";
      map[key] ??= { in: 0, out: 0 };
      map[key].in += ev.tokens_in;
      map[key].out += ev.tokens_out;
    }
    return Object.entries(map).map(([model, t]) => ({
      model: model.length > 20 ? model.slice(-20) : model,
      cost: estimateCost(t.in, t.out, model),
      tokens_in: t.in,
      tokens_out: t.out,
    }));
  }, [events]);

  const chartData = useMemo(() =>
    events
      .filter((e) => e.tokens_in + e.tokens_out > 0)
      .map((e, i) => ({
        i,
        in: e.tokens_in,
        out: e.tokens_out,
      })),
    [events]
  );

  return (
    <div className="space-y-4">
      <Card>
        <h3 className="text-xs font-semibold text-text-muted uppercase tracking-wider mb-3">Cost Summary</h3>
        <div className="space-y-2 font-mono text-sm">
          <div className="flex justify-between">
            <span className="text-text-muted">Tokens in</span>
            <span className="text-text-primary">{formatTokens(cost.total_tokens_in)}</span>
          </div>
          <div className="flex justify-between">
            <span className="text-text-muted">Tokens out</span>
            <span className="text-text-primary">{formatTokens(cost.total_tokens_out)}</span>
          </div>
          <div className="flex justify-between">
            <span className="text-text-muted">Events</span>
            <span className="text-text-primary">{cost.event_count}</span>
          </div>
          <div className="border-t border-border-default pt-2 flex justify-between font-semibold">
            <span className="text-text-muted">Est. cost</span>
            <span className="text-purple-brand text-base">{formatCost(totalCost)}</span>
          </div>
          <p className="text-text-muted text-xs opacity-50">* estimate based on published rates</p>
        </div>
      </Card>

      {byModel.length > 0 && (
        <Card>
          <h3 className="text-xs font-semibold text-text-muted uppercase tracking-wider mb-3">By Model</h3>
          <div className="space-y-2">
            {byModel.map((m) => (
              <div key={m.model} className="flex justify-between items-center text-xs">
                <span className="text-text-muted font-mono truncate max-w-[140px]">{m.model}</span>
                <span className="text-purple-brand font-mono">{formatCost(m.cost)}</span>
              </div>
            ))}
          </div>
        </Card>
      )}

      {chartData.length > 1 && (
        <Card>
          <h3 className="text-xs font-semibold text-text-muted uppercase tracking-wider mb-3">
            Tokens per Event
          </h3>
          <ResponsiveContainer width="100%" height={100}>
            <BarChart data={chartData} margin={{ top: 0, right: 0, left: -30, bottom: 0 }}>
              <XAxis dataKey="i" hide />
              <YAxis tick={{ fontSize: 9, fill: "#6b7280" }} />
              <Tooltip
                contentStyle={{ background: "#111827", border: "1px solid #1f2937", fontSize: 11 }}
                labelStyle={{ color: "#f9fafb" }}
              />
              <Bar dataKey="in" fill="#06b6d4" opacity={0.7} radius={[2, 2, 0, 0]} />
              <Bar dataKey="out" fill="#8b5cf6" opacity={0.7} radius={[2, 2, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
          <div className="flex gap-4 mt-1 text-xs text-text-muted">
            <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-sm bg-green-brand/70 inline-block" />in</span>
            <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-sm bg-purple-brand/70 inline-block" />out</span>
          </div>
        </Card>
      )}
    </div>
  );
}
