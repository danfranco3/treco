"use client";

import { useEffect, useRef } from "react";
import type { AgentEvent, DeviationPayload, LogPayload } from "@/lib/types";
import { getPayload } from "@/lib/types";
import { formatTime } from "@/lib/utils";

const TAG: Record<string, { label: string; srLabel: string; color: string }> = {
  ticket_started:    { label: "START",      srLabel: "START",             color: "text-green-brand" },
  criterion_checked: { label: "✓ CRIT",    srLabel: "CRITERION CHECKED", color: "text-green-brand" },
  criterion_failed:  { label: "✗ CRIT",    srLabel: "CRITERION FAILED",  color: "text-red-brand" },
  pr_opened:         { label: "PR",         srLabel: "PR",                color: "text-amber-brand" },
  done:              { label: "DONE",       srLabel: "DONE",              color: "text-green-brand" },
  error:             { label: "ERROR",      srLabel: "ERROR",             color: "text-red-brand" },
  log:               { label: "LOG",        srLabel: "LOG",               color: "text-text-muted" },
  heartbeat:         { label: "PING",       srLabel: "HEARTBEAT",        color: "text-text-muted opacity-40" },
  deviation:         { label: "⚠ DEVIATE", srLabel: "WARNING DEVIATION", color: "text-amber-500" },
};

interface TerminalLogProps {
  events: AgentEvent[];
  agentNames?: Record<string, string>;
  maxLines?: number;
}

export function TerminalLog({ events, agentNames = {}, maxLines = 200 }: TerminalLogProps) {
  const bottomRef = useRef<HTMLDivElement>(null);
  const prevLen = useRef(0);

  useEffect(() => {
    if (events.length > prevLen.current) {
      bottomRef.current?.scrollIntoView({ behavior: "smooth" });
      prevLen.current = events.length;
    }
  }, [events.length]);

  const lines = [...events].reverse().slice(0, maxLines).reverse();

  return (
    <div
      role="log"
      aria-label="Live event stream"
      aria-live="polite"
      aria-relevant="additions"
      className="font-mono text-xs bg-[#070b13] rounded-xl border border-border-default h-full overflow-y-auto p-3 space-y-0.5"
    >
      {lines.length === 0 && (
        <p className="text-text-muted opacity-50 text-center py-8">no events yet</p>
      )}
      {lines.map((ev, i) => {
        const tag = TAG[ev.event_type] ?? { label: ev.event_type, srLabel: ev.event_type, color: "text-text-muted" };
        const isDeviation = ev.event_type === "deviation";
        const isHeartbeat = ev.event_type === "heartbeat";
        const agentName = agentNames[ev.agent_id];
        const isNewest = i === lines.length - 1;

        const msg = isDeviation
          ? getPayload<DeviationPayload>(ev).message
          : getPayload<LogPayload>(ev).message;
        const url = isDeviation ? undefined : getPayload<LogPayload>(ev).url;
        const deviationType = isDeviation ? getPayload<DeviationPayload>(ev).deviation_type : undefined;

        return (
          <div
            key={ev.id}
            className={isNewest ? "terminal-line-enter" : undefined}
          >
            <span className="text-text-muted select-none">{formatTime(ev.created_at)} </span>
            <span className={`font-semibold ${tag.color}`} aria-label={tag.srLabel}>
              <span aria-hidden="true">[{tag.label}]</span>
            </span>
            {deviationType && (
              <span className="mx-1 text-amber-500 font-mono text-xs">{deviationType}</span>
            )}
            {agentName && !isHeartbeat && (
              <span className="mx-1 px-1.5 py-0 rounded bg-surface text-text-muted">{agentName}</span>
            )}
            {msg && <span className={`ml-1 ${isDeviation ? "text-amber-400" : "text-text-primary"}`}>{msg}</span>}
            {url && (
              <a
                href={url}
                target="_blank"
                rel="noopener noreferrer"
                className="ml-1 text-green-brand underline underline-offset-2"
                aria-label={`Open link (opens in new tab): ${url}`}
              >
                {url}
              </a>
            )}
          </div>
        );
      })}
      <div ref={bottomRef} />
    </div>
  );
}
