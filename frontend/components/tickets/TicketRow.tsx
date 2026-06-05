import Link from "next/link";
import type { Ticket } from "@/lib/types";
import { Badge } from "@/components/ui/Badge";
import { criteriaProgress } from "@/lib/utils";

export function TicketRow({ ticket }: { ticket: Ticket }) {
  const pct = criteriaProgress(ticket.acceptance_criteria);
  const done = ticket.acceptance_criteria.filter((c) => c.done).length;
  const total = ticket.acceptance_criteria.length;
  const color = pct === 100 ? "bg-green-brand" : pct > 50 ? "bg-cyan-brand" : "bg-amber-brand";

  return (
    <Link href={`/tickets/${ticket.id}`}>
      <div className="flex items-center gap-4 px-4 py-3 hover:bg-surface-2 rounded-lg transition-colors group">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-1">
            <Badge label={ticket.source} />
            {ticket.source_id && (
              <span className="text-text-muted text-xs font-mono">{ticket.source_id}</span>
            )}
          </div>
          <p className="text-sm text-text-primary group-hover:text-cyan-brand transition-colors truncate">
            {ticket.title}
          </p>
        </div>

        <div className="flex items-center gap-4 flex-shrink-0">
          <div className="text-right">
            <p className="text-xs text-text-muted font-mono">{done}/{total}</p>
            <p className="text-xs text-text-muted">criteria</p>
          </div>
          <div className="w-24">
            <div className="flex justify-between text-xs text-text-muted mb-1">
              <span>{pct}%</span>
            </div>
            <div className="h-1.5 bg-surface-2 rounded-full overflow-hidden">
              <div
                className={`h-full rounded-full transition-all duration-500 ${color}`}
                style={{ width: `${pct}%` }}
              />
            </div>
          </div>
          <Badge label={ticket.status} />
        </div>
      </div>
    </Link>
  );
}
