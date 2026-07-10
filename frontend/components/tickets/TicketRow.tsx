"use client";

import Link from "next/link";
import type { Ticket } from "@/lib/types";
import { Badge } from "@/components/ui/Badge";
import { criteriaProgress } from "@/lib/utils";

function MiniProgressRing({ pct }: { pct: number }) {
  const r = 9;
  const circ = 2 * Math.PI * r;
  const offset = circ * (1 - pct / 100);

  return (
    <svg width={24} height={24} viewBox="0 0 24 24" fill="none" className="-rotate-90" aria-hidden="true">
      <circle cx="12" cy="12" r={r} stroke="var(--surface-2)" strokeWidth={2.5} />
      <circle
        cx="12" cy="12" r={r}
        stroke="var(--green)"
        strokeWidth={2.5}
        strokeLinecap="round"
        strokeDasharray={circ}
        strokeDashoffset={offset}
        style={{ transition: "stroke-dashoffset 500ms ease" }}
      />
    </svg>
  );
}

export function TicketRow({
  ticket,
  onContextMenu,
}: {
  ticket: Ticket;
  onContextMenu?: (e: React.MouseEvent, ticket: Ticket) => void;
}) {
  const pct = criteriaProgress(ticket.acceptance_criteria);
  const verified = ticket.acceptance_criteria.filter((c) => c.verified).length;
  const total = ticket.acceptance_criteria.length;

  return (
    <Link
      href={`/tickets/${ticket.id}`}
      onContextMenu={(e) => onContextMenu?.(e, ticket)}
      className="flex items-center gap-4 px-4 py-3 hover:bg-[var(--surface-3)] transition-colors duration-75"
    >
      <div className="flex-1 min-w-0">
        <span className="text-sm text-[var(--text)] truncate block">{ticket.title}</span>
        {total > 0 && (
          <span className="text-xs text-[var(--text-3)]">
            {verified} verified · {total - verified} remaining
          </span>
        )}
      </div>
      <Badge label={ticket.status} />
      <MiniProgressRing pct={pct} />
    </Link>
  );
}
