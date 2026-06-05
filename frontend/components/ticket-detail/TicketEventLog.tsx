import type { Agent, AgentEvent } from "@/lib/types";
import { TerminalLog } from "@/components/ui/TerminalLog";

interface TicketEventLogProps {
  events: AgentEvent[];
  agents: Agent[];
}

export function TicketEventLog({ events, agents }: TicketEventLogProps) {
  const agentNames = Object.fromEntries(agents.map((a) => [a.id, a.name]));
  return (
    <div className="flex flex-col h-full">
      <h3 className="text-xs font-semibold text-text-muted uppercase tracking-wider mb-2">
        Event Log
      </h3>
      <div className="flex-1 min-h-0">
        <TerminalLog events={events} agentNames={agentNames} />
      </div>
    </div>
  );
}
