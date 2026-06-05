import type { Agent, Ticket } from "@/lib/types";
import { AgentMiniCard } from "./AgentMiniCard";
import { EmptyState } from "@/components/ui/EmptyState";

interface AgentStatusGridProps {
  agents: Agent[];
  tickets: Ticket[];
}

export function AgentStatusGrid({ agents, tickets }: AgentStatusGridProps) {
  if (!agents.length) {
    return <EmptyState icon="◎" title="No agents registered" sub="Create an agent via the API to get started" />;
  }

  const ticketMap = Object.fromEntries(tickets.map((t) => [t.id, t]));

  return (
    <div className="grid grid-cols-2 xl:grid-cols-3 gap-3">
      {agents.map((agent) => (
        <AgentMiniCard
          key={agent.id}
          agent={agent}
          ticket={agent.current_ticket_id ? ticketMap[agent.current_ticket_id] : undefined}
        />
      ))}
    </div>
  );
}
