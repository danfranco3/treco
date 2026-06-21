"use client";

import { useMemo } from "react";
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer
} from "recharts";
import type { AgentEvent } from "@/lib/types";

interface DashboardBurndownProps {
  events: AgentEvent[];
}

export function DashboardBurndown({ events }: DashboardBurndownProps) {
  const data = useMemo(() => {
    const checkEvents = events
      .filter((e) => e.event_type === "criterion_checked")
      .sort((a, b) => new Date(a.created_at).getTime() - new Date(b.created_at).getTime());

    if (!checkEvents.length) return [];

    const buckets: Record<string, number> = {};
    for (const ev of checkEvents) {
      const d = new Date(ev.created_at);
      d.setMinutes(0, 0, 0);
      const key = d.toISOString();
      buckets[key] = (buckets[key] ?? 0) + 1;
    }

    let running = 0;
    return Object.entries(buckets)
      .sort(([a], [b]) => a.localeCompare(b))
      .map(([time, count]) => {
        running += count;
        return {
          time: new Date(time).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
          completed: running,
          delta: count,
        };
      });
  }, [events]);

  if (!data.length) {
    return (
      <div className="flex items-center justify-center h-32 text-text-muted text-xs">
        no criteria completed yet
      </div>
    );
  }

  return (
    <div role="img" aria-label={`Criteria burndown chart — ${data[data.length - 1]?.completed ?? 0} criteria completed`}>
    <ResponsiveContainer width="100%" height={160}>
      <LineChart data={data} margin={{ top: 4, right: 8, left: -20, bottom: 0 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="#1f2937" />
        <XAxis dataKey="time" tick={{ fontSize: 10, fill: "#6b7280" }} />
        <YAxis tick={{ fontSize: 10, fill: "#6b7280" }} />
        <Tooltip
          contentStyle={{ background: "#111827", border: "1px solid #1f2937", borderRadius: 8, fontSize: 11 }}
          labelStyle={{ color: "#f9fafb" }}
          itemStyle={{ color: "#10b981" }}
        />
        <Line
          type="monotone"
          dataKey="completed"
          stroke="#10b981"
          strokeWidth={2}
          dot={{ fill: "#10b981", r: 3 }}
          activeDot={{ r: 5 }}
        />
      </LineChart>
    </ResponsiveContainer>
    </div>
  );
}
