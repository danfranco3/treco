"use client";

import { useParams } from "next/navigation";
import Link from "next/link";
import { useWorkspace } from "@/lib/workspace";
import { useAgents, useTicket, useTicketCost, useTicketEvents } from "@/lib/hooks";
import { ProgressRing } from "@/components/ui/ProgressRing";
import { Badge } from "@/components/ui/Badge";
import { Spinner } from "@/components/ui/Spinner";
import { CriteriaChecklist } from "@/components/ticket-detail/CriteriaChecklist";
import { TicketEventLog } from "@/components/ticket-detail/TicketEventLog";
import { CostPanel } from "@/components/ticket-detail/CostPanel";
import { criteriaProgress } from "@/lib/utils";

export default function TicketDetailPage() {
  const { id } = useParams<{ id: string }>();
  const { workspaceId } = useWorkspace();

  const { data: ticket, isLoading: ticketLoading } = useTicket(id);
  const { data: events = [] } = useTicketEvents(id);
  const { data: cost } = useTicketCost(id);
  const { data: agents = [] } = useAgents(workspaceId);

  const agentNames = Object.fromEntries(agents.map((a) => [a.id, a.name]));

  if (ticketLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <Spinner className="h-8 w-8" />
      </div>
    );
  }

  if (!ticket) {
    return <p className="text-text-muted text-sm">Ticket not found.</p>;
  }

  const pct = criteriaProgress(ticket.acceptance_criteria);
  const activeAgent = agents.find((a) => a.current_ticket_id === ticket.id);

  return (
    <div className="flex flex-col gap-6 max-w-6xl mx-auto">
      {/* Header */}
      <div className="flex items-start gap-4">
        <Link href="/tickets" className="text-text-muted hover:text-text-primary text-sm mt-1">← back</Link>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-1">
            <Badge label={ticket.source} />
            {ticket.source_id && (
              <span className="text-text-muted text-xs font-mono">{ticket.source_id}</span>
            )}
            <Badge label={ticket.status} />
            {activeAgent && (
              <span className="flex items-center gap-1.5 text-xs text-cyan-brand bg-cyan-brand/10 border border-cyan-brand/30 px-2 py-0.5 rounded-full">
                <span className="relative flex h-1.5 w-1.5">
                  <span className="ping-slow absolute inline-flex h-full w-full rounded-full bg-cyan-brand opacity-75" />
                  <span className="relative inline-flex rounded-full h-1.5 w-1.5 bg-cyan-brand" />
                </span>
                {activeAgent.name} working
              </span>
            )}
          </div>
          <h1 className="text-2xl font-bold text-text-primary">{ticket.title}</h1>
          {ticket.description && (
            <p className="text-text-muted text-sm mt-2 line-clamp-3">{ticket.description}</p>
          )}
        </div>
        <ProgressRing pct={pct} label="complete" />
      </div>

      {/* Main grid */}
      <div className="grid grid-cols-3 gap-6">
        {/* Criteria — 2 cols */}
        <div className="col-span-2 flex flex-col gap-4">
          <div className="flex items-center justify-between">
            <h2 className="text-sm font-semibold text-text-primary">
              Acceptance Criteria
              <span className="ml-2 text-text-muted font-normal">
                {ticket.acceptance_criteria.filter((c) => c.done).length}/{ticket.acceptance_criteria.length}
              </span>
            </h2>
          </div>
          <CriteriaChecklist criteria={ticket.acceptance_criteria} events={events} agentNames={agentNames} />

          {/* Event log */}
          <div className="mt-2" style={{ height: 320 }}>
            <TicketEventLog events={events} agents={agents} />
          </div>
        </div>

        {/* Cost panel — 1 col */}
        <div>
          {cost ? (
            <CostPanel cost={cost} events={events} />
          ) : (
            <div className="flex items-center justify-center h-32 text-text-muted text-xs">
              no cost data yet
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
