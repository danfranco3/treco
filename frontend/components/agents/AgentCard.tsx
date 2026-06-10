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

const INDICATOR: Record<string, string> = {
  working: "bg-[var(--cyan)]",
  done:    "bg-[var(--green)]",
  error:   "bg-[var(--red)]",
  idle:    "bg-[var(--border)]",
};

export function AgentCard({ agent, ticket, totalTokensIn = 0, totalTokensOut = 0 }: AgentCardProps) {
  const isWorking = agent.status === "working";
  const isError   = agent.status === "error";
  const pct       = ticket ? criteriaProgress(ticket.acceptance_criteria) : 0;
  const indicatorColor = INDICATOR[agent.status] ?? INDICATOR.idle;

  return (
    <div className={cn(
      "relative bg-[var(--surface)] border border-[var(--border)] rounded-xl p-4 pl-5 flex flex-col gap-3",
      "transition-colors duration-200",
      isError && "border-[var(--red)]/20",
    )}>
      {/* 3px left indicator bar — pulses only when working */}
      <span
        className={cn(
          "absolute left-0 top-3 bottom-3 w-[3px] rounded-r-full",
          indicatorColor,
          isWorking && "agent-working",
        )}
      />

      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <PulseRing active={isWorking} error={isError} />
          <Link
            href={`/agents/${agent.id}`}
            className="font-semibold text-sm text-[var(--text)] hover:text-[var(--cyan)] transition-colors font-mono"
          >
            {agent.name}
          </Link>
        </div>
        {(totalTokensIn + totalTokensOut) > 0 && (
          <CostPill tokensIn={totalTokensIn} tokensOut={totalTokensOut} />
        )}
      </div>

      {ticket ? (
        <Link href={`/tickets/${ticket.id}`} className="group">
          <div className="bg-[var(--surface-2)] rounded-lg px-3 py-2.5 border border-[var(--border)] group-hover:border-[var(--cyan)]/30 transition-colors">
            <p className="text-xs text-[var(--text-2)] truncate group-hover:text-[var(--text)] transition-colors">
              {ticket.title}
            </p>
            <div className="mt-2 flex items-center gap-2">
              <div className="flex-1 h-1 bg-[var(--bg)] rounded-full overflow-hidden">
                <div
                  className={cn(
                    "h-full rounded-full transition-all duration-500",
                    pct === 100 ? "bg-[var(--green)]" : "bg-[var(--cyan)]/60",
                  )}
                  style={{ width: `${pct}%` }}
                />
              </div>
              <span className="text-xs text-[var(--text-3)] font-mono tabular-nums">{pct}%</span>
            </div>
          </div>
        </Link>
      ) : (
        <p className="text-xs text-[var(--text-3)]">no active ticket</p>
      )}

      {isError && (
        <p className="text-xs text-[var(--red)] bg-[var(--red)]/10 rounded px-2 py-1">
          last run failed
        </p>
      )}
    </div>
  );
}
