"use client";

import { useWorkspace } from "@/lib/workspace";
import { useAgents, useTickets, useWorkspaceEvents } from "@/lib/hooks";
import { StatBar } from "@/components/dashboard/StatBar";
import { AgentStatusGrid } from "@/components/dashboard/AgentStatusGrid";
import { EventFeed } from "@/components/dashboard/EventFeed";
import { Card } from "@/components/ui/Card";
import { Spinner } from "@/components/ui/Spinner";
import { OnboardingCard } from "@/components/dashboard/OnboardingCard";

export default function DashboardPage() {
  const { workspaceId } = useWorkspace();
  const { data: agents = [], isLoading: agentsLoading } = useAgents(workspaceId);
  const { data: tickets = [], isLoading: ticketsLoading } = useTickets(workspaceId);
  const { data: rawEvents = [] } = useWorkspaceEvents(workspaceId);

  // Chronological order for charts/feed; workspace events arrive newest-first from API
  const events = [...rawEvents].sort(
    (a, b) => new Date(a.created_at).getTime() - new Date(b.created_at).getTime()
  );

  const loading = agentsLoading || ticketsLoading;
  const isEmpty = !loading && agents.length === 0 && tickets.length === 0;

  return (
    <div className="flex flex-col gap-6 h-full">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-bold text-text-primary">Dashboard</h1>
        {loading && <Spinner />}
      </div>

      {isEmpty && <OnboardingCard workspaceId={workspaceId} />}

      <StatBar agents={agents} tickets={tickets} events={events} />

      <div className="grid grid-cols-3 gap-6 flex-1 min-h-0">
        <div className="col-span-2">
          <Card>
            <h2 className="text-sm font-semibold text-text-primary mb-4">Agents</h2>
            <AgentStatusGrid agents={agents} tickets={tickets} events={events} />
          </Card>
        </div>

        <Card className="flex flex-col min-h-0" style={{ height: "calc(100vh - 280px)" }}>
          <EventFeed events={events} agents={agents} />
        </Card>
      </div>
    </div>
  );
}
