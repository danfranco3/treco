"use client";

import { useState } from "react";
import { useWorkspace } from "@/lib/workspace";
import { useAgents, useTickets } from "@/lib/hooks";
import { AgentColumn } from "@/components/agents/AgentColumn";
import { RegisterAgentModal } from "@/components/agents/RegisterAgentModal";
import { Spinner } from "@/components/ui/Spinner";

export default function AgentsPage() {
  const { workspaceId } = useWorkspace();
  const { data: agents = [], isLoading, mutate: refetchAgents } = useAgents(workspaceId);
  const { data: tickets = [] } = useTickets(workspaceId);
  const [showRegister, setShowRegister] = useState(false);

  const working = agents.filter((a) => a.status === "working");
  const idle = agents.filter((a) => a.status === "idle" || a.status === "done");
  const error = agents.filter((a) => a.status === "error");
  const noneWorking = working.length === 0 && agents.length > 0;

  return (
    <div className="flex flex-col gap-6">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-bold text-text-primary">Agents</h1>
        <div className="flex items-center gap-3">
          <span className="text-xs text-text-muted">{agents.length} total</span>
          {isLoading && <Spinner />}
          <button
            onClick={() => setShowRegister(true)}
            className="text-xs bg-cyan-brand/10 border border-cyan-brand/40 text-cyan-brand hover:bg-cyan-brand/20 px-3 py-1.5 rounded-lg transition-colors"
          >
            + Register agent
          </button>
        </div>
      </div>

      {noneWorking && (
        <div className="border border-dashed border-border-default rounded-xl px-4 py-3 text-xs text-text-muted">
          No agents running. In a terminal:{" "}
          <code className="font-mono text-cyan-brand">treco start</code>
          {" — or assign a ticket to an idle agent from the "}
          <a href="/tickets" className="underline hover:text-text-primary">Tickets</a>
          {" page."}
        </div>
      )}

      <div className="grid grid-cols-3 gap-6">
        <AgentColumn title="Working" agents={working} tickets={tickets} />
        <AgentColumn title="Idle"    agents={idle}    tickets={tickets} />
        <AgentColumn title="Error"   agents={error}   tickets={tickets} />
      </div>

      {showRegister && (
        <RegisterAgentModal
          workspaceId={workspaceId}
          onClose={() => setShowRegister(false)}
          onCreated={() => refetchAgents()}
        />
      )}
    </div>
  );
}
