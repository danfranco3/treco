"use client";

import { useWorkspace } from "@/lib/workspace";
import { useAgents, useTickets, useWorkspaceEvents } from "@/lib/hooks";
import { useWorkspaceStream, useAgentStream } from "@/lib/hooks";
import { BoardColumn } from "@/components/dashboard/BoardColumn";
import { TicketCard } from "@/components/dashboard/TicketCard";
import { criteriaProgress } from "@/lib/utils";
import type { Agent, AgentEvent, Ticket } from "@/lib/types";

// ── helpers ──────────────────────────────────────────────────────────────────

function lastLogEvent(events: AgentEvent[], ticketId: string): AgentEvent | null {
  const mine = events.filter(
    (e) => e.ticket_id === ticketId && e.event_type === "log" && e.payload?.message
  );
  return mine.length ? mine[mine.length - 1] : null;
}

function latestEventTime(events: AgentEvent[], ticketId: string): number {
  const ts = events
    .filter((e) => e.ticket_id === ticketId)
    .map((e) => new Date(e.created_at).getTime());
  return ts.length ? Math.max(...ts) : 0;
}

const DONE_WINDOW_MS = 24 * 60 * 60 * 1000;

// ── page ─────────────────────────────────────────────────────────────────────

export default function DashboardPage() {
  const { workspaceId } = useWorkspace();

  const { data: tickets = [] } = useTickets(workspaceId);
  const { data: agents  = [] } = useAgents(workspaceId);
  const { data: events  = [] } = useWorkspaceEvents(workspaceId);

  // live SSE pushes
  useWorkspaceStream(workspaceId);
  useAgentStream(workspaceId);

  // agent keyed by current_ticket_id
  const agentByTicket: Record<string, Agent> = {};
  for (const a of agents) {
    if (a.current_ticket_id) agentByTicket[a.current_ticket_id] = a;
  }

  // bucket tickets
  const todo:      Ticket[] = [];
  const inProgress: Ticket[] = [];
  const blocked:   Ticket[] = [];
  const done:      Ticket[] = [];

  const now = Date.now();

  for (const t of tickets) {
    const agent = agentByTicket[t.id] ?? null;

    if (agent?.status === "working") {
      inProgress.push(t);
    } else if (agent?.status === "awaiting_approval" || agent?.status === "error") {
      blocked.push(t);
    } else if (t.status === "done") {
      const latest = latestEventTime(events, t.id);
      if (latest && now - latest < DONE_WINDOW_MS) done.push(t);
    } else {
      // open, no active agent
      todo.push(t);
    }
  }

  // sort In Progress: highest % first (closest to done)
  inProgress.sort(
    (a, b) => criteriaProgress(b.acceptance_criteria) - criteriaProgress(a.acceptance_criteria)
  );

  // sort Blocked: most recent event first
  blocked.sort((a, b) => latestEventTime(events, b.id) - latestEventTime(events, a.id));

  // sort Todo: newest ticket first (by created_at fallback via event time)
  todo.sort((a, b) => latestEventTime(events, b.id) - latestEventTime(events, a.id));

  // sort Done: most recently completed first
  done.sort((a, b) => latestEventTime(events, b.id) - latestEventTime(events, a.id));

  const columns = [
    { key: "todo",       title: "Todo",        color: "neutral" as const, tickets: todo.slice(0, 20) },
    { key: "inProgress", title: "In Progress",  color: "blue"    as const, tickets: inProgress.slice(0, 20) },
    { key: "blocked",    title: "Blocked",      color: "amber"   as const, tickets: blocked.slice(0, 20) },
    { key: "done",       title: "Done",         color: "green"   as const, tickets: done.slice(0, 20) },
  ];

  return (
    <div className="flex flex-col gap-4 h-full">
      <h1 className="text-xl font-bold text-[var(--text)]">Activity</h1>

      <div className="grid grid-cols-4 gap-3 flex-1 min-h-0 overflow-x-auto">
        {columns.map(({ key, title, color, tickets: col }) => (
          <BoardColumn key={key} title={title} color={color} count={col.length}>
            {col.map((t) => (
              <TicketCard
                key={t.id}
                ticket={t}
                agent={agentByTicket[t.id] ?? null}
                lastEvent={lastLogEvent(events, t.id)}
              />
            ))}
          </BoardColumn>
        ))}
      </div>
    </div>
  );
}
