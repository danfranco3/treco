import type { Agent, Ticket } from "@/lib/types";
import { AgentCard } from "./AgentCard";
import { cn } from "@/lib/utils";

const COLUMN_STYLES: Record<string, { header: string; dot: string }> = {
  Working: { header: "text-cyan-brand", dot: "bg-cyan-brand" },
  Idle:    { header: "text-text-muted",  dot: "bg-gray-600" },
  Error:   { header: "text-red-brand",   dot: "bg-red-brand" },
};

interface AgentColumnProps {
  title: string;
  agents: Agent[];
  tickets: Ticket[];
}

export function AgentColumn({ title, agents, tickets }: AgentColumnProps) {
  const style = COLUMN_STYLES[title] ?? COLUMN_STYLES["Idle"];
  const ticketMap = Object.fromEntries(tickets.map((t) => [t.id, t]));

  return (
    <div className="flex flex-col gap-3">
      <div className="flex items-center gap-2 px-1">
        <span className={cn("h-2 w-2 rounded-full flex-shrink-0", style.dot)} />
        <h2 className={cn("text-sm font-semibold", style.header)}>{title}</h2>
        <span className="text-xs text-text-muted ml-auto">{agents.length}</span>
      </div>

      {agents.length === 0 && (
        <div className="border border-dashed border-border-default rounded-xl px-4 py-8 text-center text-text-muted text-xs">
          none
        </div>
      )}

      {agents.map((agent) => (
        <AgentCard
          key={agent.id}
          agent={agent}
          ticket={agent.current_ticket_id ? ticketMap[agent.current_ticket_id] : undefined}
        />
      ))}
    </div>
  );
}
