/**
 * Permission gate UI — the ticket detail view must surface a pending
 * permission_requested event and route the user's Allow/Deny to the
 * CORRECT agent's permission_response endpoint.
 *
 * Data hooks and the API layer are mocked (jsdom has no backend); the real
 * TicketDetailClient component tree renders and drives the assertions.
 */
import React from "react";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import "@testing-library/jest-dom";

import type { Agent, AgentEvent, Ticket } from "@/lib/types";

const mockRespondPermission = jest.fn().mockResolvedValue({ ok: true });

jest.mock("next/navigation", () => ({
  useParams: () => ({ id: "ticket-1" }),
  useRouter: () => ({ push: jest.fn(), back: jest.fn() }),
}));
jest.mock("swr", () => ({
  useSWRConfig: () => ({ mutate: jest.fn() }),
}));
jest.mock("@/lib/workspace", () => ({
  useWorkspace: () => ({ workspaceId: "ws1" }),
}));
jest.mock("@/lib/api", () => ({
  updateTicketCriteria: jest.fn(),
  refineTicket: jest.fn(),
  implementTicket: jest.fn(),
  respondPermission: (...args: unknown[]) => mockRespondPermission(...args),
  pauseAgent: jest.fn(),
  resumeAgent: jest.fn(),
}));
jest.mock("@/lib/impl-settings", () => ({
  loadImplSettings: () => ({ model: "m", system_prompt: "", skip_permissions: false }),
}));
// Heavy visual children (recharts, virtualized logs) are stubbed — they are
// not under test here and do not render meaningfully in jsdom.
jest.mock("@/components/ticket-detail/TicketEventLog", () => ({
  TicketEventLog: () => <div data-testid="event-log" />,
}));
jest.mock("@/components/control-tower/TraceTree", () => ({
  TraceTree: () => <div data-testid="trace-tree" />,
}));
jest.mock("@/components/telemetry/MetricsPanel", () => ({
  MetricsPanel: () => <div data-testid="metrics" />,
}));
jest.mock("@/components/tickets/TicketRow", () => ({
  TicketRow: () => <div data-testid="ticket-row" />,
}));

const hookData: Record<string, unknown> = {};
jest.mock("@/lib/hooks", () => ({
  useTicket: () => ({ data: hookData.ticket, isLoading: false, error: undefined }),
  useTicketEvents: () => ({ data: hookData.events ?? [] }),
  useAgents: () => ({ data: hookData.agents ?? [] }),
  useTicketTraces: () => ({ data: [] }),
  useTicketTelemetry: () => ({ data: [] }),
  useTickets: () => ({ data: [] }),
  useTier: () => ({ data: { tier: "free", max_parallel_agents: 1 } }),
}));

import { TicketDetailClient } from "@/app/(app)/tickets/[id]/TicketDetailClient";

const ticket: Ticket = {
  id: "ticket-1",
  workspace_id: "ws1",
  source: "custom",
  source_id: null,
  title: "Gated ticket",
  description: null,
  status: "hitl_review",
  acceptance_criteria: [],
  body: {},
  git_branch: null,
  worktree_path: null,
  external_ref: null,
};

const gatedAgent: Agent = {
  id: "agent-gated",
  name: "impl-agent",
  status: "awaiting_approval",
  current_ticket_id: "ticket-1",
  workspace_id: "ws1",
} as Agent;

const otherAgent: Agent = {
  id: "agent-other",
  name: "other-agent",
  status: "working",
  current_ticket_id: "ticket-999",
  workspace_id: "ws1",
} as Agent;

function permissionEvent(overrides: Partial<AgentEvent> = {}): AgentEvent {
  return {
    id: "evt-perm",
    agent_id: "agent-gated",
    ticket_id: "ticket-1",
    workspace_id: "ws1",
    event_type: "permission_requested",
    criterion_id: null,
    tokens_in: 0,
    tokens_out: 0,
    model: null,
    payload: { prompt: "Run rm -rf build?" },
    created_at: new Date().toISOString(),
    ...overrides,
  } as AgentEvent;
}

beforeEach(() => {
  jest.clearAllMocks();
  hookData.ticket = ticket;
  hookData.events = [];
  hookData.agents = [];
});

describe("pending permission surfaces on the ticket detail view", () => {
  it("shows the permission prompt when the last event is permission_requested", () => {
    hookData.events = [permissionEvent()];
    hookData.agents = [gatedAgent, otherAgent];
    render(<TicketDetailClient />);

    expect(screen.getByText("Agent requesting permission")).toBeInTheDocument();
    expect(screen.getByText("Run rm -rf build?")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Allow" })).toBeEnabled();
    expect(screen.getByRole("button", { name: "Deny" })).toBeEnabled();
  });

  it("hides the panel when a later event supersedes the request", () => {
    hookData.events = [
      permissionEvent(),
      permissionEvent({ id: "evt-log", event_type: "log", payload: { message: "resumed" } }),
    ];
    hookData.agents = [gatedAgent];
    render(<TicketDetailClient />);

    expect(screen.queryByText("Agent requesting permission")).not.toBeInTheDocument();
  });

  it("hides the panel when no agent is active on this ticket", () => {
    hookData.events = [permissionEvent()];
    hookData.agents = [otherAgent];
    render(<TicketDetailClient />);

    expect(screen.queryByText("Agent requesting permission")).not.toBeInTheDocument();
  });
});

describe("responding targets the correct agent", () => {
  it("Allow sends y to the agent working THIS ticket, not any other agent", async () => {
    hookData.events = [permissionEvent()];
    hookData.agents = [otherAgent, gatedAgent];
    render(<TicketDetailClient />);

    await userEvent.click(screen.getByRole("button", { name: "Allow" }));

    await waitFor(() => expect(mockRespondPermission).toHaveBeenCalledTimes(1));
    expect(mockRespondPermission).toHaveBeenCalledWith("agent-gated", "y");
  });

  it("Deny sends n to the gated agent", async () => {
    hookData.events = [permissionEvent()];
    hookData.agents = [gatedAgent];
    render(<TicketDetailClient />);

    await userEvent.click(screen.getByRole("button", { name: "Deny" }));

    await waitFor(() => expect(mockRespondPermission).toHaveBeenCalledTimes(1));
    expect(mockRespondPermission).toHaveBeenCalledWith("agent-gated", "n");
  });

  it("buttons disable while the response is in flight", async () => {
    let resolve!: (v: { ok: boolean }) => void;
    mockRespondPermission.mockReturnValueOnce(
      new Promise((r) => { resolve = r; })
    );
    hookData.events = [permissionEvent()];
    hookData.agents = [gatedAgent];
    render(<TicketDetailClient />);

    await userEvent.click(screen.getByRole("button", { name: "Allow" }));
    expect(screen.getByRole("button", { name: "Allowing…" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Deny" })).toBeDisabled();

    resolve({ ok: true });
    await waitFor(() =>
      expect(screen.getByRole("button", { name: "Allow" })).toBeEnabled()
    );
  });
});
