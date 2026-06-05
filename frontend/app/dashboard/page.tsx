"use client";

import { useMemo } from "react";
import { useWorkspace } from "@/lib/workspace";
import { useAgents, useTicketEvents, useTickets } from "@/lib/hooks";
import { StatBar } from "@/components/dashboard/StatBar";
import { AgentStatusGrid } from "@/components/dashboard/AgentStatusGrid";
import { EventFeed } from "@/components/dashboard/EventFeed";
import { DashboardBurndown } from "@/components/dashboard/DashboardBurndown";
import { Card } from "@/components/ui/Card";
import { Spinner } from "@/components/ui/Spinner";

function useActiveEvents(activeTicketIds: string[]) {
  // SWR rules require hooks at top level — we fetch the first 6 active tickets' events
  const e0 = useTicketEvents(activeTicketIds[0] ?? "");
  const e1 = useTicketEvents(activeTicketIds[1] ?? "");
  const e2 = useTicketEvents(activeTicketIds[2] ?? "");
  const e3 = useTicketEvents(activeTicketIds[3] ?? "");
  const e4 = useTicketEvents(activeTicketIds[4] ?? "");
  const e5 = useTicketEvents(activeTicketIds[5] ?? "");

  return [e0, e1, e2, e3, e4, e5]
    .flatMap((r) => r.data ?? [])
    .sort((a, b) => new Date(a.created_at).getTime() - new Date(b.created_at).getTime());
}

export default function DashboardPage() {
  const { workspaceId } = useWorkspace();
  const { data: agents = [], isLoading: agentsLoading } = useAgents(workspaceId);
  const { data: tickets = [], isLoading: ticketsLoading } = useTickets(workspaceId);

  const activeTicketIds = useMemo(
    () => agents.filter((a) => a.current_ticket_id).map((a) => a.current_ticket_id!).slice(0, 6),
    [agents]
  );

  const events = useActiveEvents(activeTicketIds);

  const loading = agentsLoading || ticketsLoading;

  return (
    <div className="flex flex-col gap-6 h-full">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-bold text-text-primary">Dashboard</h1>
        {loading && <Spinner />}
      </div>

      <StatBar agents={agents} tickets={tickets} events={events} />

      <div className="grid grid-cols-3 gap-6 flex-1 min-h-0">
        <div className="col-span-2 flex flex-col gap-6">
          <Card>
            <h2 className="text-sm font-semibold text-text-primary mb-4">Agents</h2>
            <AgentStatusGrid agents={agents} tickets={tickets} />
          </Card>

          <Card>
            <div className="flex items-center justify-between mb-3">
              <h2 className="text-sm font-semibold text-text-primary">Criteria Burndown</h2>
              <span className="text-xs text-text-muted">today</span>
            </div>
            <DashboardBurndown events={events} />
          </Card>
        </div>

        <Card className="flex flex-col min-h-0" style={{ height: "calc(100vh - 280px)" }}>
          <EventFeed events={events} agents={agents} />
        </Card>
      </div>
    </div>
  );
}
