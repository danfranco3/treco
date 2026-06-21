import Link from "next/link";
import type { Agent, AgentEvent, Ticket, DeviationPayload } from "@/lib/types";
import { PulseRing } from "@/components/ui/PulseRing";
import { Badge } from "@/components/ui/Badge";
import { cn, criteriaProgress } from "@/lib/utils";
import { getPayload } from "@/lib/types";

interface AgentMiniCardProps {
  agent: Agent;
  ticket?: Ticket;
  deviation?: AgentEvent;
}

const DEVIATION_LABELS: Record<string, (ev: AgentEvent) => string> = {
  stuck: (ev) => `stuck ${getPayload<DeviationPayload>(ev).context?.minutes_silent ?? "?"}m`,
  incomplete_criteria: () => "incomplete criteria",
  token_spike: () => "token spike",
  process_exited: () => "process exited",
  awaiting_approval: () => "needs approval",
};

export function AgentMiniCard({ agent, ticket, deviation }: AgentMiniCardProps) {
  const hasDeviation = !!deviation;
  const isWorking = agent.status === "working";
  const isError = agent.status === "error";
  const isAwaitingApproval = agent.status === "awaiting_approval";

  const deviationPayload = deviation ? getPayload<DeviationPayload>(deviation) : undefined;
  const deviationType = deviationPayload?.deviation_type;
  const deviationLabel = deviation && deviationType ? DEVIATION_LABELS[deviationType]?.(deviation) ?? deviationType : undefined;

  return (
    <div
      className={cn(
        "bg-surface border rounded-xl p-4 transition-all duration-300",
        isWorking && !hasDeviation && "agent-working border-green-brand/20",
        isError && !hasDeviation && "border-red-brand/30",
        (hasDeviation || isAwaitingApproval) && "border-amber-500/40 bg-amber-500/5",
        !isWorking && !isError && !hasDeviation && !isAwaitingApproval && "border-border-default"
      )}
    >
      <div className="flex items-start justify-between gap-2">
        <div className="flex items-center gap-2 min-w-0">
          <PulseRing active={isWorking && !hasDeviation} error={isError || hasDeviation || isAwaitingApproval} size="sm" />
          <span className="text-sm font-medium text-text-primary truncate">{agent.name}</span>
          {deviationLabel && (
            <span
              className="text-amber-500 text-xs font-medium flex items-center gap-1"
              title={deviationPayload?.message}
              aria-label={`Warning: ${deviationLabel}${deviationPayload?.message ? ` — ${deviationPayload.message}` : ""}`}
            >
              <span aria-hidden="true">⚠</span> {deviationLabel}
            </span>
          )}
        </div>
        <Badge label={agent.status} />
      </div>

      {ticket && isWorking && (
        <Link
          href={`/tickets/${ticket.id}`}
          aria-label={`View ticket: ${ticket.title}`}
          className="mt-3 block group"
        >
          <p className="text-xs text-text-muted group-hover:text-green-brand transition-colors truncate">
            {ticket.title}
          </p>
          <div
            role="progressbar"
            aria-valuenow={criteriaProgress(ticket.acceptance_criteria)}
            aria-valuemin={0}
            aria-valuemax={100}
            aria-label="Criteria completion"
            className="mt-1.5 h-1 bg-surface-2 rounded-full overflow-hidden"
          >
            <div
              aria-hidden="true"
              className="h-full bg-green-brand/60 rounded-full transition-all duration-500"
              style={{ width: `${criteriaProgress(ticket.acceptance_criteria)}%` }}
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
