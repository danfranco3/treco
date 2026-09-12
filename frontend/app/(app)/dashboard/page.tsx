"use client";

import { useState } from "react";
import { useWorkspace } from "@/lib/workspace";
import { useAgents, useTickets, useWorkspaceEvents } from "@/lib/hooks";
import { useWorkspaceStream, useAgentStream } from "@/lib/hooks";
import { BoardColumn } from "@/components/dashboard/BoardColumn";
import { TicketCard } from "@/components/dashboard/TicketCard";
import { TicketContextMenu } from "@/components/tickets/TicketContextMenu";
import { deleteTicket, implementTicket } from "@/lib/api";
import { loadImplSettings } from "@/lib/impl-settings";
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

  const { data: tickets = [], mutate } = useTickets(workspaceId);
  const { data: agents  = [] } = useAgents(workspaceId);
  const { data: events  = [] } = useWorkspaceEvents(workspaceId);

  // live SSE pushes
  useWorkspaceStream(workspaceId);
  useAgentStream(workspaceId);

  const [menu, setMenu] = useState<{ x: number; y: number; ticket: Ticket } | null>(null);

  function handleContextMenu(e: React.MouseEvent, ticket: Ticket) {
    e.preventDefault();
    setMenu({ x: e.clientX, y: e.clientY, ticket });
  }

  async function handleDelete(ticket: Ticket) {
    await deleteTicket(ticket.id);
    mutate();
  }

  async function handleImplement(ticket: Ticket) {
    const s = loadImplSettings();
    await implementTicket(ticket.id, { method: "claude_code", model: s.model, system_prompt: s.system_prompt, skip_permissions: s.skip_permissions });
    mutate();
  }

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
    if (t.status === "in_progress") {
      inProgress.push(t);
    } else if (t.status === "blocked" || t.status === "hitl_review") {
      blocked.push(t);
    } else if (t.status === "done") {
      const latest = latestEventTime(events, t.id);
      if (latest && now - latest < DONE_WINDOW_MS) done.push(t);
    } else {
      // backlog / open
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
                onContextMenu={handleContextMenu}
              />
            ))}
          </BoardColumn>
        ))}
      </div>

      {menu && (
        <TicketContextMenu
          x={menu.x}
          y={menu.y}
          onImplement={() => handleImplement(menu.ticket)}
          onDelete={() => handleDelete(menu.ticket)}
          onClose={() => setMenu(null)}
        />
      )}
    </div>
  );
}
