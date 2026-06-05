import Link from "next/link";
import type { Agent, Ticket } from "@/lib/types";
import { PulseRing } from "@/components/ui/PulseRing";
import { Badge } from "@/components/ui/Badge";
import { cn } from "@/lib/utils";

interface AgentMiniCardProps {
  agent: Agent;
  ticket?: Ticket;
}

export function AgentMiniCard({ agent, ticket }: AgentMiniCardProps) {
  const isWorking = agent.status === "working";
  const isError = agent.status === "error";

  return (
    <div
      className={cn(
        "bg-surface border rounded-xl p-4 transition-all duration-300",
        isWorking && "agent-working border-cyan-brand/20",
        isError && "border-red-brand/30",
        !isWorking && !isError && "border-border-default"
      )}
    >
      <div className="flex items-start justify-between gap-2">
        <div className="flex items-center gap-2 min-w-0">
          <PulseRing active={isWorking} error={isError} size="sm" />
          <span className="text-sm font-medium text-text-primary truncate">{agent.name}</span>
        </div>
        <Badge label={agent.status} />
      </div>

      {ticket && isWorking && (
        <Link href={`/tickets/${ticket.id}`} className="mt-3 block group">
          <p className="text-xs text-text-muted group-hover:text-cyan-brand transition-colors truncate">
            {ticket.title}
          </p>
          <div className="mt-1.5 h-1 bg-surface-2 rounded-full overflow-hidden">
            <div
              className="h-full bg-cyan-brand/60 rounded-full transition-all duration-500"
              style={{
                width: `${ticket.acceptance_criteria.length
                  ? Math.round((ticket.acceptance_criteria.filter((c) => c.done).length / ticket.acceptance_criteria.length) * 100)
                  : 0}%`,
              }}
            />
          </div>
        </Link>
      )}

      {!ticket && isWorking && (
        <p className="mt-2 text-xs text-text-muted opacity-50">loading ticket…</p>
      )}
    </div>
  );
}
