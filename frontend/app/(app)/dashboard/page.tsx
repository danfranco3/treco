"use client";

import { useWorkspace } from "@/lib/workspace";
import { useAgents, useWorkspaceEvents } from "@/lib/hooks";
import { EventFeed } from "@/components/dashboard/EventFeed";
import { Card } from "@/components/ui/Card";

export default function DashboardPage() {
  const { workspaceId } = useWorkspace();
  const { data: agents = [] } = useAgents(workspaceId);
  const { data: rawEvents = [] } = useWorkspaceEvents(workspaceId);

  const events = [...rawEvents].sort(
    (a, b) => new Date(a.created_at).getTime() - new Date(b.created_at).getTime()
  );

  return (
    <div className="flex flex-col gap-6 h-full">
      <h1 className="text-xl font-bold text-[var(--text)]">Activity</h1>
      <Card className="flex flex-col min-h-0 flex-1" style={{ height: "calc(100vh - 160px)" }}>
        <EventFeed events={events} agents={agents} />
      </Card>
    </div>
  );
}
