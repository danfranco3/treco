import Link from "next/link";
import type { Ticket } from "@/lib/types";
import { Badge } from "@/components/ui/Badge";
import { criteriaProgress } from "@/lib/utils";

function MiniProgressRing({ pct }: { pct: number }) {
  const r = 9;
  const circ = 2 * Math.PI * r;
  const offset = circ * (1 - pct / 100);
  const color = pct === 100 ? "var(--green)" : pct > 50 ? "var(--cyan)" : "var(--amber)";

  return (
    <svg width={24} height={24} viewBox="0 0 24 24" fill="none" className="-rotate-90" aria-hidden="true">
      <circle cx="12" cy="12" r={r} stroke="var(--surface-2)" strokeWidth={2.5} />
      <circle
        cx="12"
        cy="12"
        r={r}
        stroke={color}
        strokeWidth={2.5}
        strokeLinecap="round"
        strokeDasharray={circ}
        strokeDashoffset={offset}
        style={{ transition: "stroke-dashoffset 500ms ease" }}
      />
    </svg>
  );
}

export function TicketRow({ ticket }: { ticket: Ticket }) {
  const pct = criteriaProgress(ticket.acceptance_criteria);

  return (
    <Link href={`/tickets/${ticket.id}`}>
      <div
        className="grid items-center gap-4 px-4 py-2.5 hover:bg-[var(--surface-3)] transition-colors duration-75"
        style={{ gridTemplateColumns: "1fr 90px 90px 36px" }}
      >
        <div className="min-w-0 flex items-center gap-2">
          <span className="font-mono text-xs text-[var(--text-3)] flex-shrink-0">
            {ticket.source_id ?? ticket.source}
          </span>
          <span className="text-sm text-[var(--text)] truncate">
            {ticket.title}
          </span>
        </div>

        <Badge label={ticket.source} />

        <div className="flex items-center justify-center">
          <Badge label={ticket.status} />
        </div>

        <div className="flex items-center justify-center">
          <MiniProgressRing pct={pct} />
        </div>
      </div>
    </Link>
  );
}
