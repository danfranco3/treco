"use client";

import { useWorkspace } from "@/lib/workspace";
import { useAgents, useTickets } from "@/lib/hooks";

export function TopBar() {
  const { workspaceId } = useWorkspace();
  const { data: agents } = useAgents(workspaceId);
  const { data: tickets } = useTickets(workspaceId);
  const workingAgents = agents?.filter((a) => a.status === "working" && a.current_ticket_id) ?? [];

  return (
    <header className="h-14 flex items-center gap-2 px-6 border-b border-[var(--border)] bg-[var(--surface)] flex-shrink-0 overflow-x-auto">
      {workingAgents.map((agent) => {
        const ticket = tickets?.find((t) => t.id === agent.current_ticket_id);
        return (
          <div
            key={agent.id}
            aria-live="polite"
            className="flex items-center gap-1.5 text-xs bg-[var(--green-3)] border border-[var(--green)]/25 text-[var(--green-badge-text)] px-2.5 py-1 rounded-full font-medium whitespace-nowrap"
          >
            <span className="relative flex h-1.5 w-1.5">
              <span className="ping-slow absolute inline-flex h-full w-full rounded-full bg-[var(--green)] opacity-75" />
              <span className="relative inline-flex rounded-full h-1.5 w-1.5 bg-[var(--green)]" />
            </span>
            {ticket?.title ?? agent.name}
          </div>
        );
      })}
    </header>
  );
}
