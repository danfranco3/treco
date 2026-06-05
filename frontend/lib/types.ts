export interface Criterion {
  id: string;
  text: string;
  done: boolean;
}

export interface Ticket {
  id: string;
  source: "jira" | "linear" | "asana" | "github" | "custom";
  source_id: string | null;
  title: string;
  description: string | null;
  status: string;
  acceptance_criteria: Criterion[];
  body: Record<string, unknown>;
}

export interface Agent {
  id: string;
  name: string;
  status: "idle" | "working" | "done" | "error";
  current_ticket_id: string | null;
  workspace_id: string;
}

export type EventType =
  | "ticket_started"
  | "criterion_checked"
  | "criterion_failed"
  | "pr_opened"
  | "done"
  | "error"
  | "log";

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

export interface CostSummary {
  ticket_id: string;
  total_tokens_in: number;
  total_tokens_out: number;
  event_count: number;
}
