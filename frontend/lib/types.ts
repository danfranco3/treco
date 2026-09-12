export interface Criterion {
  id: string;
  text: string;
  test_cmd: string | null;
  done: boolean;
  verified: boolean;
  evidence: string | null;
  file_path: string | null;
  notes: string | null;
}

export type TicketStatus =
  | "backlog"
  | "open"
  | "in_progress"
  | "hitl_review"
  | "blocked"
  | "done";

export interface ExternalRef {
  provider: "jira" | "linear";
  issue_key: string;
  issue_url?: string;
  last_synced_at?: string;
  sync_status?: "ok" | "error";
  sync_error?: string | null;
}

export interface Ticket {
  id: string;
  workspace_id: string | null;
  source: "jira" | "linear" | "asana" | "github" | "custom";
  source_id: string | null;
  title: string;
  description: string | null;
  status: TicketStatus;
  acceptance_criteria: Criterion[];
  body: Record<string, unknown>;
  git_branch?: string | null;
  worktree_path?: string | null;
  external_ref?: ExternalRef | null;
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
  status: "idle" | "working" | "awaiting_approval" | "done" | "error" | "blocked" | "cloud_offloaded";
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
  | "deviation"
  | "permission_requested";

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

export type TraceStepType =
  | "tool_call"
  | "llm_turn"
  | "test_run"
  | "criterion_check"
  | "permission_gate";

export interface TraceNode {
  id: string;
  agent_id: string;
  ticket_id: string;
  parent_trace_id: string | null;
  event_id: string | null;
  step_type: TraceStepType;
  tool_name: string | null;
  status: "running" | "ok" | "error" | "skipped";
  tokens_in: number;
  tokens_out: number;
  duration_ms: number | null;
  payload: Record<string, unknown>;
  created_at: string;
  children: TraceNode[];
}

export interface MetricRow {
  id: string;
  workspace_id: string;
  ticket_id: string | null;
  agent_id: string | null;
  metric: string;
  value: number;
  unit: "tokens" | "usd" | "ms" | "count" | "ratio";
  dims: Record<string, unknown>;
  created_at: string;
}

export interface TierInfo {
  tier: "free" | "pro" | "team";
  max_parallel_agents: number;
}

export interface CostSummary {
  ticket_id: string;
  total_tokens_in: number;
  total_tokens_out: number;
  event_count: number;
}

export interface UserProfile {
  id: string;
  github_id: string;
  login: string;
  avatar_url: string | null;
}
