import Link from "next/link";
import type { Agent, Ticket } from "@/lib/types";
import { PulseRing } from "@/components/ui/PulseRing";
import { CostPill } from "@/components/ui/CostPill";
import { cn, criteriaProgress } from "@/lib/utils";

interface AgentCardProps {
  agent: Agent;
  ticket?: Ticket;
  totalTokensIn?: number;
  totalTokensOut?: number;
}

export function AgentCard({ agent, ticket, totalTokensIn = 0, totalTokensOut = 0 }: AgentCardProps) {
  const isWorking = agent.status === "working";
  const isError = agent.status === "error";
  const pct = ticket ? criteriaProgress(ticket.acceptance_criteria) : 0;

  return (
    <div className={cn(
      "bg-surface border rounded-xl p-4 flex flex-col gap-3 transition-all duration-300",
      isWorking && "agent-working border-cyan-brand/20",
      isError && "border-red-brand/30 bg-red-brand/5",
      !isWorking && !isError && "border-border-default"
    )}>
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <PulseRing active={isWorking} error={isError} />
          <span className="font-semibold text-text-primary">{agent.name}</span>
        </div>
        {(totalTokensIn + totalTokensOut) > 0 && (
          <CostPill tokensIn={totalTokensIn} tokensOut={totalTokensOut} />
        )}
      </div>

      {ticket && (
        <Link href={`/tickets/${ticket.id}`} className="group">
          <div className="bg-surface-2 rounded-lg p-3 border border-border-default group-hover:border-cyan-brand/30 transition-colors">
            <div className="flex items-center gap-2 mb-2">
              <span className="text-xs text-text-muted font-mono">{ticket.source_id ?? ticket.source}</span>
            </div>
            <p className="text-sm text-text-primary group-hover:text-cyan-brand transition-colors truncate">
              {ticket.title}
            </p>
            <div className="mt-2 flex items-center gap-2">
              <div className="flex-1 h-1.5 bg-bg rounded-full overflow-hidden">
                <div
                  className={cn(
                    "h-full rounded-full transition-all duration-500",
                    pct === 100 ? "bg-green-brand" : "bg-cyan-brand/60"
                  )}
                  style={{ width: `${pct}%` }}
                />
              </div>
              <span className="text-xs text-text-muted font-mono">{pct}%</span>
            </div>
          </div>
        </Link>
      )}

      {isError && (
        <p className="text-xs text-red-brand bg-red-brand/10 rounded px-2 py-1">
          last run failed
        </p>
      )}
    </div>
  );
}
