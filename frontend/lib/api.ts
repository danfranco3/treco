import type { Agent, AgentEvent, CostSummary, MetricRow, Ticket, TierInfo, TraceNode, Workspace } from "./types";

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

async function patch<T>(path: string, body: unknown): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    throw new Error(`API ${res.status}: ${await res.text()}`);
  }
  return res.json() as Promise<T>;
}

async function del(path: string): Promise<void> {
  const res = await fetch(`${BASE}${path}`, { method: "DELETE" });
  if (!res.ok) {
    throw new Error(`API ${res.status}: ${await res.text()}`);
  }
}

export interface CreateTicketRequest {
  workspace_id?: string;
  title: string;
  description?: string;
  acceptance_criteria?: string[];
}

export const createTicket = (data: CreateTicketRequest): Promise<Ticket> =>
  post("/tickets", data);

export const fetchTickets = (workspaceId?: string, limit = 50, offset = 0): Promise<Ticket[]> => {
  const params = new URLSearchParams({ limit: String(limit), offset: String(offset) });
  if (workspaceId) params.set("workspace_id", workspaceId);
  return get(`/tickets?${params.toString()}`);
};

export const fetchTicket = (ticketId: string): Promise<Ticket> =>
  get(`/tickets/${ticketId}`);

export const deleteTicket = (ticketId: string): Promise<void> =>
  del(`/tickets/${ticketId}`);

export interface CriterionInput {
  id?: string;
  text: string;
  test_cmd?: string | null;
  done?: boolean;
  verified?: boolean;
  evidence?: string | null;
  file_path?: string | null;
  notes?: string | null;
}

export const updateTicketCriteria = (ticketId: string, criteria: CriterionInput[]): Promise<Ticket> => {
  const res = fetch(`/api/tickets/${ticketId}/criteria`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(criteria),
  });
  return res.then(async (r) => {
    if (!r.ok) throw new Error(`API ${r.status}: ${await r.text()}`);
    return r.json();
  });
};

export const refineTicket = (ticketId: string): Promise<Ticket> =>
  post(`/tickets/${ticketId}/refine`, {});

export interface ImplementTicketRequest {
  method: "claude_code" | "anthropic";
  model: string;
  system_prompt: string;
  skip_permissions: boolean;
}

export const implementTicket = (
  ticketId: string,
  data: ImplementTicketRequest
): Promise<{ agent_id: string; agent_name: string }> =>
  post(`/tickets/${ticketId}/implement`, data);

export const respondPermission = (
  agentId: string,
  response: "y" | "n"
): Promise<{ ok: boolean }> =>
  post(`/agents/${agentId}/permission_response`, { response });

export const fetchAgents = (workspaceId: string): Promise<Agent[]> =>
  get(`/agents?workspace_id=${workspaceId}`);

export const fetchTicketEvents = (ticketId: string): Promise<AgentEvent[]> =>
  get(`/events/ticket/${ticketId}`);

export const fetchTicketCost = (ticketId: string): Promise<CostSummary> =>
  get(`/events/ticket/${ticketId}/cost`);

export const fetchWorkspaceEvents = (workspaceId: string, limit = 100): Promise<AgentEvent[]> =>
  get(`/events/?workspace_id=${workspaceId}&limit=${limit}`);


export const fetchTicketTraces = (ticketId: string): Promise<TraceNode[]> =>
  get(`/traces/ticket/${ticketId}`);

export const fetchTicketTelemetry = (ticketId: string): Promise<MetricRow[]> =>
  get(`/telemetry/ticket/${ticketId}`);

export const fetchWorkspaceTelemetry = (workspaceId: string): Promise<MetricRow[]> =>
  get(`/telemetry/workspace/${workspaceId}/summary`);

export const fetchTier = (): Promise<TierInfo> => get("/meta/tier");

export const pauseAgent = (agentId: string): Promise<Agent> =>
  post(`/agents/${agentId}/pause`, {});

export const resumeAgent = (agentId: string): Promise<Agent> =>
  post(`/agents/${agentId}/resume`, {});

export const fetchWorkspaces = (): Promise<Workspace[]> => get("/workspaces");

export const fetchWorkspace = (workspaceId: string): Promise<Workspace> =>
  get(`/workspaces/${workspaceId}`);

export const updateWorkspace = (
  workspaceId: string,
  data: { name?: string; repo_path?: string }
): Promise<Workspace> => patch(`/workspaces/${workspaceId}`, data);
