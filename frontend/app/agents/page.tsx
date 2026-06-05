"use client";

import { useWorkspace } from "@/lib/workspace";
import { useAgents, useTickets } from "@/lib/hooks";
import { AgentColumn } from "@/components/agents/AgentColumn";
import { Spinner } from "@/components/ui/Spinner";

export default function AgentsPage() {
  const { workspaceId } = useWorkspace();
  const { data: agents = [], isLoading } = useAgents(workspaceId);
  const { data: tickets = [] } = useTickets(workspaceId);

  const working = agents.filter((a) => a.status === "working");
  const idle = agents.filter((a) => a.status === "idle" || a.status === "done");
  const error = agents.filter((a) => a.status === "error");

  return (
    <div className="flex flex-col gap-6">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-bold text-text-primary">Agents</h1>
        <div className="flex items-center gap-3">
          <span className="text-xs text-text-muted">{agents.length} total</span>
          {isLoading && <Spinner />}
        </div>
      </div>

      <div className="grid grid-cols-3 gap-6">
        <AgentColumn title="Working" agents={working} tickets={tickets} />
        <AgentColumn title="Idle"    agents={idle}    tickets={tickets} />
        <AgentColumn title="Error"   agents={error}   tickets={tickets} />
      </div>
    </div>
  );
}
