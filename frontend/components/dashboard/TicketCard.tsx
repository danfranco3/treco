"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import type { Agent, AgentEvent, Ticket } from "@/lib/types";
import { criteriaProgress, formatRelativeTime } from "@/lib/utils";
import { cn } from "@/lib/utils";

interface TicketCardProps {
  ticket: Ticket;
  agent: Agent | null;
  lastEvent: AgentEvent | null;
  onContextMenu?: (e: React.MouseEvent, ticket: Ticket) => void;
}

function lastMessage(event: AgentEvent | null): string | null {
  if (!event) return null;
  const msg = event.payload?.message;
  return typeof msg === "string" ? msg : null;
}

function timeAgo(event: AgentEvent | null, ticket: Ticket): string {
  const iso = event?.created_at ?? (ticket as unknown as { created_at?: string }).created_at;
  return iso ? formatRelativeTime(iso) : "";
}

export function TicketCard({ ticket, agent, lastEvent, onContextMenu }: TicketCardProps) {
  const router = useRouter();
  const [, forceUpdate] = useState(0);

  useEffect(() => {
    const id = setInterval(() => forceUpdate((n) => n + 1), 10_000);
    return () => clearInterval(id);
  }, []);

  const pct = criteriaProgress(ticket.acceptance_criteria);
  const hasCriteria = ticket.acceptance_criteria.length > 0;
  const msg = lastMessage(lastEvent);
  const ago = timeAgo(lastEvent, ticket);

  const isAwaiting = agent?.status === "awaiting_approval";
  const isError = agent?.status === "error";

  return (
    <div
      role="button"
      tabIndex={0}
      onClick={() => router.push(`/tickets/${ticket.id}`)}
      onKeyDown={(e) => e.key === "Enter" && router.push(`/tickets/${ticket.id}`)}
      onContextMenu={(e) => onContextMenu?.(e, ticket)}
      className={cn(
        "bg-[var(--surface)] border border-[var(--border)] rounded-lg p-3 flex flex-col gap-2",
        "cursor-pointer transition-shadow hover:shadow-md focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--green)]",
        isAwaiting && "border-l-[3px] border-l-[var(--amber)]",
        isError    && "border-l-[3px] border-l-[var(--red)]",
      )}
    >
      {/* Title */}
      <p className="text-[13px] font-medium text-[var(--text)] leading-snug line-clamp-2">
        {ticket.title}
      </p>

      {/* Progress */}
      {hasCriteria ? (
        <div className="flex items-center gap-2">
          <div className="flex-1 h-1 rounded-full bg-[var(--surface-3)] overflow-hidden">
            <div
              className="h-full rounded-full bg-[var(--green)] transition-all duration-500"
              style={{ width: `${pct}%` }}
            />
          </div>
          <span className="text-[11px] font-semibold tabular-nums text-[var(--text-2)] min-w-[28px] text-right">
            {pct}%
          </span>
        </div>
      ) : (
        <p className="text-[11px] text-[var(--text-3)]">
          {ticket.acceptance_criteria.length === 0 ? "No criteria" : ""}
        </p>
      )}

      {/* Last action — only when agent active */}
      {agent && msg && (
        <div
          className={cn(
            "text-[11px] font-mono rounded px-2 py-1 truncate",
            isAwaiting
              ? "text-[var(--amber)] bg-[var(--amber-bg,#fef3c7)]"
              : isError
              ? "text-[var(--red)] bg-[var(--red-bg,#fef2f2)]"
              : "text-[var(--text-3)] bg-[var(--surface-2)]"
          )}
        >
          {!isAwaiting && !isError && (
            <span className="inline-block w-1.5 h-1.5 rounded-full bg-[var(--green)] mr-1.5 align-middle animate-pulse" />
          )}
          {msg}
        </div>
      )}

      {/* Footer */}
      <div className="flex items-center justify-between text-[11px] text-[var(--text-3)]">
        <span className="font-mono truncate max-w-[60%]">
          {agent ? agent.name : <span className="opacity-60">no agent</span>}
        </span>
        <span className="tabular-nums">{ago}</span>
      </div>
    </div>
  );
}
