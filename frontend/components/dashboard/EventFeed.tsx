import type { Agent, AgentEvent } from "@/lib/types";
import { TerminalLog } from "@/components/ui/TerminalLog";

interface EventFeedProps {
  events: AgentEvent[];
  agents: Agent[];
}

export function EventFeed({ events, agents }: EventFeedProps) {
  const agentNames = Object.fromEntries(agents.map((a) => [a.id, a.name]));

  return (
    <div className="flex flex-col h-full">
      <div className="flex items-center justify-between mb-3">
        <h2 className="text-sm font-semibold text-text-primary">Live Event Stream</h2>
        <span className="text-xs text-text-muted font-mono">{events.length} events</span>
      </div>
      <div className="flex-1 min-h-0">
        <TerminalLog events={events} agentNames={agentNames} />
      </div>
    </div>
  );
}
