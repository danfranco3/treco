export interface Criterion {
  id: string;
  text: string;
  done: boolean;
}

export interface Ticket {
  id: string;
  workspace_id: string | null;
  source: "jira" | "linear" | "asana" | "github" | "custom";
  source_id: string | null;
  title: string;
  description: string | null;
  status: string;
  acceptance_criteria: Criterion[];
  body: Record<string, unknown>;
}

export interface Workspace {
  id: string;
  name: string;
  repo_path: string | null;
  created_at: string;
}

export interface Agent {
  id: string;
  name: string;
  status: "idle" | "working" | "awaiting_approval" | "done" | "error";
  current_ticket_id: string | null;
  workspace_id: string;
}

export type DeviationType =
  | "stuck"
  | "incomplete_criteria"
  | "token_spike"
  | "process_exited"
  | "awaiting_approval";

export type EventType =
  | "ticket_started"
  | "criterion_checked"
  | "criterion_failed"
  | "pr_opened"
  | "done"
  | "error"
  | "log"
  | "heartbeat"
  | "deviation";

export interface AgentEvent {
  id: string;
  agent_id: string;
  ticket_id: string;
  workspace_id: string;
  event_type: EventType;
  criterion_id: string | null;
  tokens_in: number;
  tokens_out: number;
  model: string | null;
  payload: Record<string, unknown>;
  created_at: string;
}

export interface DeviationPayload {
  deviation_type?: string;
  severity?: "warning" | "error";
  message?: string;
  context?: Record<string, unknown>;
}

export interface LogPayload {
  message?: string;
  url?: string;
}

export function getPayload<T>(event: AgentEvent): T {
  return event.payload as T;
}

export interface CostSummary {
  ticket_id: string;
  total_tokens_in: number;
  total_tokens_out: number;
  event_count: number;
}
