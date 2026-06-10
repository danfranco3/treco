"use client";

import { useEffect } from "react";
import useSWR, { useSWRConfig } from "swr";
import {
  fetchAgentEvents,
  fetchAgents,
  fetchTicket,
  fetchTicketCost,
  fetchTicketEvents,
  fetchTickets,
  fetchWorkspaceEvents,
} from "./api";
import type { Agent, AgentEvent } from "./types";

// ── polling hooks (SSE is primary; these are fallback / initial load) ─────────

export function useTickets(workspaceId: string) {
  return useSWR(
    workspaceId ? ["tickets", workspaceId] : null,
    () => fetchTickets(workspaceId),
    { refreshInterval: 30_000, revalidateOnFocus: false }
  );
}

export function useTicket(ticketId: string) {
  return useSWR(
    ticketId ? ["ticket", ticketId] : null,
    () => fetchTicket(ticketId),
    { refreshInterval: 30_000, revalidateOnFocus: false }
  );
}

export function useAgents(workspaceId: string) {
  return useSWR(
    workspaceId ? ["agents", workspaceId] : null,
    () => fetchAgents(workspaceId),
    { refreshInterval: 30_000, revalidateOnFocus: false }
  );
}

export function useTicketEvents(ticketId: string) {
  return useSWR(
    ticketId ? ["events", ticketId] : null,
    () => fetchTicketEvents(ticketId),
    { refreshInterval: 30_000, revalidateOnFocus: false }
  );
}

export function useTicketCost(ticketId: string) {
  return useSWR(
    ticketId ? ["cost", ticketId] : null,
    () => fetchTicketCost(ticketId),
    { refreshInterval: 30_000, revalidateOnFocus: false }
  );
}

export function useWorkspaceEvents(workspaceId: string) {
  return useSWR(
    workspaceId ? ["workspace-events", workspaceId] : null,
    () => fetchWorkspaceEvents(workspaceId),
    { refreshInterval: 30_000, revalidateOnFocus: false }
  );
}

export function useAgentEvents(agentId: string) {
  return useSWR(
    agentId ? ["agent-events", agentId] : null,
    () => fetchAgentEvents(agentId),
    { refreshInterval: 30_000, revalidateOnFocus: false }
  );
}

// ── SSE stream hooks ──────────────────────────────────────────────────────────

export function useWorkspaceStream(workspaceId: string) {
  const { mutate } = useSWRConfig();

  useEffect(() => {
    if (!workspaceId) return;

    const es = new EventSource(
      `/api/events/stream?workspace_id=${encodeURIComponent(workspaceId)}`
    );

    es.onmessage = (e: MessageEvent<string>) => {
      const event: AgentEvent = JSON.parse(e.data);

      // Push into per-ticket cache instantly
      mutate(
        ["events", event.ticket_id],
        (prev: AgentEvent[] = []) =>
          prev.some((ev) => ev.id === event.id) ? prev : [...prev, event],
        { revalidate: false }
      );

      // Push into workspace-level event cache
      mutate(
        ["workspace-events", workspaceId],
        (prev: AgentEvent[] = []) =>
          prev.some((ev) => ev.id === event.id) ? prev : [...prev, event],
        { revalidate: false }
      );

      // Revalidate ticket state + cost totals
      mutate(["ticket", event.ticket_id]);
      mutate(["cost", event.ticket_id]);
    };

    // EventSource reconnects automatically — no manual retry needed
    return () => es.close();
  }, [workspaceId, mutate]);
}

export function useAgentStream(workspaceId: string) {
  const { mutate } = useSWRConfig();

  useEffect(() => {
    if (!workspaceId) return;

    const es = new EventSource(
      `/api/agents/stream?workspace_id=${encodeURIComponent(workspaceId)}`
    );

    es.onmessage = (e: MessageEvent<string>) => {
      const updated: Agent = JSON.parse(e.data);
      mutate(
        ["agents", workspaceId],
        (prev: Agent[] = []) =>
          prev.some((a) => a.id === updated.id)
            ? prev.map((a) => (a.id === updated.id ? { ...a, ...updated } : a))
            : [...prev, updated],
        { revalidate: false }
      );
    };

    return () => es.close();
  }, [workspaceId, mutate]);
}
