import type { Agent, AgentEvent, CostSummary, Ticket } from "./types";

const BASE = "/api";

async function get<T>(path: string): Promise<T> {
  const res = await fetch(`${BASE}${path}`, { cache: "no-store" });
  if (!res.ok) {
    throw new Error(`API ${res.status}: ${await res.text()}`);
  }
  return res.json() as Promise<T>;
}

export const fetchTickets = (workspaceId: string): Promise<Ticket[]> =>
  get(`/tickets/?workspace_id=${workspaceId}`);

export const fetchTicket = (ticketId: string): Promise<Ticket> =>
  get(`/tickets/${ticketId}`);

export const fetchAgents = (workspaceId: string): Promise<Agent[]> =>
  get(`/agents/?workspace_id=${workspaceId}`);

export const fetchTicketEvents = (ticketId: string): Promise<AgentEvent[]> =>
  get(`/events/ticket/${ticketId}`);

export const fetchTicketCost = (ticketId: string): Promise<CostSummary> =>
  get(`/events/ticket/${ticketId}/cost`);
