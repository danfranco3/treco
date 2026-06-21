import type { Agent, AgentEvent, Ticket } from "@/lib/types";
import { AgentMiniCard } from "./AgentMiniCard";
import { EmptyState } from "@/components/ui/EmptyState";
import { Bot } from "lucide-react";
import { toMap } from "@/lib/utils";

const DEVIATION_WINDOW_MS = 30 * 60 * 1000; // 30 minutes

interface AgentStatusGridProps {
  agents: Agent[];
  tickets: Ticket[];
  events?: AgentEvent[];
}

export function AgentStatusGrid({ agents, tickets, events = [] }: AgentStatusGridProps) {
  if (!agents.length) {
    return <EmptyState Icon={Bot} title="No agents registered" sub="Create an agent via the API to get started" />;
  }

  const ticketMap = toMap(tickets);
  const cutoff = Date.now() - DEVIATION_WINDOW_MS;

  const latestDeviationByAgent = new Map<string, AgentEvent>();
  for (const ev of events) {
    if (ev.event_type !== "deviation" || new Date(ev.created_at).getTime() <= cutoff) continue;
    const prev = latestDeviationByAgent.get(ev.agent_id);
    if (!prev || new Date(ev.created_at) > new Date(prev.created_at)) {
      latestDeviationByAgent.set(ev.agent_id, ev);
    }
  }

  return (
    <ul role="list" className="grid grid-cols-2 xl:grid-cols-3 gap-3">
      {agents.map((agent) => (
        <li key={agent.id}>
          <AgentMiniCard
            agent={agent}
            ticket={agent.current_ticket_id ? ticketMap[agent.current_ticket_id] : undefined}
            deviation={latestDeviationByAgent.get(agent.id)}
          />
        </li>
      ))}
    </ul>
  );
}
