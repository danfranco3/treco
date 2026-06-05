"use client";

import { useEffect, useRef } from "react";
import type { AgentEvent } from "@/lib/types";
import { formatTime } from "@/lib/utils";

const TAG: Record<string, { label: string; color: string }> = {
  ticket_started:    { label: "START",  color: "text-cyan-brand" },
  criterion_checked: { label: "✓ CRIT", color: "text-green-brand" },
  criterion_failed:  { label: "✗ CRIT", color: "text-red-brand" },
  pr_opened:         { label: "PR",     color: "text-amber-brand" },
  done:              { label: "DONE",   color: "text-green-brand" },
  error:             { label: "ERROR",  color: "text-red-brand" },
  log:               { label: "LOG",    color: "text-text-muted" },
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
    <div className="font-mono text-xs bg-[#070b13] rounded-xl border border-border-default h-full overflow-y-auto p-3 space-y-0.5">
      {lines.length === 0 && (
        <p className="text-text-muted opacity-50 text-center py-8">no events yet</p>
      )}
      {lines.map((ev, i) => {
        const tag = TAG[ev.event_type] ?? { label: ev.event_type, color: "text-text-muted" };
        const msg = (ev.payload.message as string | undefined) ?? "";
        const url = ev.payload.url as string | undefined;
        const agentName = agentNames[ev.agent_id];
        const isNewest = i === lines.length - 1;

        return (
          <div
            key={ev.id}
            className={isNewest ? "terminal-line-enter" : undefined}
          >
            <span className="text-text-muted select-none">{formatTime(ev.created_at)} </span>
            <span className={`font-semibold ${tag.color}`}>[{tag.label}]</span>
            {agentName && (
              <span className="mx-1 px-1.5 py-0 rounded bg-surface text-text-muted">{agentName}</span>
            )}
            {msg && <span className="text-text-primary ml-1">{msg}</span>}
            {url && (
              <a href={url} target="_blank" rel="noopener noreferrer" className="ml-1 text-cyan-brand underline underline-offset-2">
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
