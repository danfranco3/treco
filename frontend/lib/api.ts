import type { Agent, AgentEvent, CostSummary, Ticket } from "./types";

const BASE = "/api";

async function get<T>(path: string): Promise<T> {
  const res = await fetch(`${BASE}${path}`, { cache: "no-store" });
  if (!res.ok) {
    throw new Error(`API ${res.status}: ${await res.text()}`);
  }
  return res.json() as Promise<T>;
}

async function post<T>(path: string, body: unknown): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    throw new Error(`API ${res.status}: ${await res.text()}`);
  }
  return res.json() as Promise<T>;
}

export interface CreateTicketRequest {
  workspace_id: string;
  title: string;
  description?: string;
  acceptance_criteria?: string[];
}

export const createTicket = (data: CreateTicketRequest): Promise<Ticket> =>
  post("/tickets/", data);

export const fetchGitHubIssues = (
  workspaceId: string,
  repo: string,
  token: string
): Promise<Ticket[]> =>
  post("/tickets/fetch/bulk", {
    workspace_id: workspaceId,
    source: "github",
    repo,
    token,
  });

export const fetchLinearIssues = (
  workspaceId: string,
  teamKey: string,
  apiKey: string
): Promise<Ticket[]> =>
  post("/tickets/fetch/bulk", {
    workspace_id: workspaceId,
    source: "linear",
    team_key: teamKey,
    api_key: apiKey,
  });

export const importTicket = (
  data: CreateTicketRequest & { source_id?: string; source?: string }
): Promise<Ticket> => post("/tickets/import", data);

export const fetchTickets = (workspaceId: string, limit = 50, offset = 0): Promise<Ticket[]> =>
  get(`/tickets/?workspace_id=${workspaceId}&limit=${limit}&offset=${offset}`);

export const fetchTicket = (ticketId: string): Promise<Ticket> =>
  get(`/tickets/${ticketId}`);

export const fetchAgents = (workspaceId: string): Promise<Agent[]> =>
  get(`/agents/?workspace_id=${workspaceId}`);

export const fetchTicketEvents = (ticketId: string): Promise<AgentEvent[]> =>
  get(`/events/ticket/${ticketId}`);

export const fetchTicketCost = (ticketId: string): Promise<CostSummary> =>
  get(`/events/ticket/${ticketId}/cost`);

export const fetchWorkspaceEvents = (workspaceId: string, limit = 100): Promise<AgentEvent[]> =>
  get(`/events/?workspace_id=${workspaceId}&limit=${limit}`);

export const fetchAgentEvents = (agentId: string, limit = 200): Promise<AgentEvent[]> =>
  get(`/events/agent/${agentId}?limit=${limit}`);

export const createAgent = (data: { workspace_id: string; name: string }) =>
  post<{ id: string; name: string; status: string; current_ticket_id: string | null; workspace_id: string; api_key: string }>(
    "/agents/",
    data
  );

export const assignTicket = (agentId: string, ticketId: string): Promise<{ ok: boolean }> =>
  post(`/agents/${agentId}/assign`, { ticket_id: ticketId });
