"use client";

import { useState, useRef, useEffect } from "react";
import { useParams, useRouter } from "next/navigation";
import { useSWRConfig } from "swr";
import { useAgents, useTicket, useTicketEvents, useTicketTelemetry, useTickets, useTicketTraces, useTier } from "@/lib/hooks";
import { useWorkspace } from "@/lib/workspace";
import { Badge } from "@/components/ui/Badge";
import { Spinner } from "@/components/ui/Spinner";
import { TicketEventLog } from "@/components/ticket-detail/TicketEventLog";
import { TraceTree } from "@/components/control-tower/TraceTree";
import { MetricsPanel } from "@/components/telemetry/MetricsPanel";
import { TicketRow } from "@/components/tickets/TicketRow";
import { EmptyState, EmptyTicketFetchError } from "@/components/ui/EmptyState";
import { Ticket as TicketIcon, ChevronDown } from "lucide-react";
import { updateTicketCriteria, refineTicket, implementTicket, respondPermission, pauseAgent, resumeAgent } from "@/lib/api";
import { loadImplSettings } from "@/lib/impl-settings";
import type { Agent, Criterion } from "@/lib/types";

type ImplMethod = "claude_code" | "anthropic";

function PollingDot({ title }: { title: string }) {
  return (
    <span title={title} className="relative flex h-3 w-3 flex-shrink-0">
      <span className="ping-slow absolute inline-flex h-full w-full rounded-full bg-green-brand opacity-75" />
      <span className="relative inline-flex rounded-full h-3 w-3 bg-green-brand" />
    </span>
  );
}

function ImplementButton({ ticketId, active, onStarted }: { ticketId: string; active: boolean; onStarted?: () => void }) {
  const [open, setOpen] = useState(false);
  const [running, setRunning] = useState(false);
  const [error, setError] = useState("");
  const ref = useRef<HTMLDivElement>(null);
  const { data: tier } = useTier();
  const cloudLocked = !tier || tier.tier === "free";

  useEffect(() => {
    function handler(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    }
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, []);

  async function launch(method: ImplMethod) {
    setOpen(false);
    setRunning(true);
    setError("");
    try {
      const s = loadImplSettings();
      await implementTicket(ticketId, { method, model: s.model, system_prompt: s.system_prompt, skip_permissions: s.skip_permissions });
      onStarted?.();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to start");
      setRunning(false);
    }
  }

  if (running || active) {
    return <PollingDot title={active ? "Agent working" : "Starting…"} />;
  }

  return (
    <div className="relative" ref={ref}>
      <button
        onClick={() => setOpen((v) => !v)}
        className="flex items-center gap-1 px-3 py-1.5 text-xs font-medium bg-[var(--green)] text-white rounded-lg hover:bg-[var(--green-2)] transition-colors"
      >
        Implement
        <ChevronDown className="w-3 h-3" />
      </button>

      {open && (
        <div className="absolute right-0 top-full mt-1 w-44 bg-[var(--surface)] border border-[var(--border)] rounded-lg shadow-lg z-10 overflow-hidden">
          <button
            onClick={() => launch("claude_code")}
            className="w-full text-left px-3 py-2.5 text-sm text-[var(--text)] hover:bg-[var(--surface-2)] transition-colors"
          >
            <span className="font-medium">Claude Code</span>
            <span className="block text-xs text-[var(--text-3)]">CLI subprocess</span>
          </button>
          <div className="border-t border-[var(--border)]" />
          <button
            onClick={() => launch("anthropic")}
            className="w-full text-left px-3 py-2.5 text-sm text-[var(--text)] hover:bg-[var(--surface-2)] transition-colors"
          >
            <span className="font-medium">Anthropic</span>
            <span className="block text-xs text-[var(--text-3)]">Built-in agent loop</span>
          </button>
          <div className="border-t border-[var(--border)]" />
          <button
            disabled={cloudLocked}
            title={cloudLocked ? "Cloud offload requires a Pro plan" : undefined}
            className="w-full text-left px-3 py-2.5 text-sm text-[var(--text)] hover:bg-[var(--surface-2)] transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
          >
            <span className="font-medium">Offload to cloud</span>
            <span className="block text-xs text-[var(--text-3)]">
              {cloudLocked ? "Pro plan required" : "Run in a micro-VM"}
            </span>
          </button>
        </div>
      )}

      {error && <p className="absolute top-full mt-1 right-0 text-xs text-red-500 whitespace-nowrap">{error}</p>}
    </div>
  );
}

function useDragResize(initial: number, min: number, max: number, invert = false) {
  const [width, setWidth] = useState(initial);

  function onMouseDown(e: React.MouseEvent) {
    e.preventDefault();
    const startX = e.clientX;
    const startW = width;
    function move(ev: MouseEvent) {
      const delta = ev.clientX - startX;
      setWidth(Math.min(max, Math.max(min, startW + (invert ? -delta : delta))));
    }
    function up() {
      document.removeEventListener("mousemove", move);
      document.removeEventListener("mouseup", up);
    }
    document.addEventListener("mousemove", move);
    document.addEventListener("mouseup", up);
  }

  return { width, onMouseDown };
}

function PaneHandle({ onMouseDown }: { onMouseDown: (e: React.MouseEvent) => void }) {
  return (
    <div
      role="separator"
      aria-orientation="vertical"
      onMouseDown={onMouseDown}
      className="hidden xl:block w-1 flex-shrink-0 cursor-col-resize rounded-full hover:bg-green-brand/40 transition-colors"
    />
  );
}

function AgentControls({ agent }: { agent: Agent }) {
  const [paused, setPaused] = useState(false);
  const [busy, setBusy] = useState(false);

  async function toggle() {
    setBusy(true);
    try {
      if (paused) {
        await resumeAgent(agent.id);
        setPaused(false);
      } else {
        await pauseAgent(agent.id);
        setPaused(true);
      }
    } catch {
      // 409 — agent state changed under us; drop back to unpaused
      setPaused(false);
    } finally {
      setBusy(false);
    }
  }

  if (agent.status !== "working") return null;

  return (
    <button
      onClick={toggle}
      disabled={busy}
      className="text-xs px-2 py-1 rounded-lg border border-border-default text-text-muted hover:text-text-primary transition-colors disabled:opacity-40"
    >
      {paused ? "▶ Resume" : "⏸ Pause"}
    </button>
  );
}

function normalizeCriterion(c: Criterion): Criterion {
  return {
    ...c,
    test_cmd: c.test_cmd ?? null,
    done: c.done ?? false,
    verified: c.verified ?? false,
    evidence: c.evidence ?? null,
    file_path: c.file_path ?? null,
    notes: c.notes ?? null,
  };
}

function CriterionDot({ c }: { c: Criterion }) {
  if (c.verified) {
    return (
      <span title="Verified by test" className="flex-shrink-0 w-4 h-4 rounded-full bg-green-brand flex items-center justify-center">
        <span className="text-white text-[9px] font-bold">✓</span>
      </span>
    );
  }
  if (c.done) {
    return (
      <span title="Claimed done (no test run)" className="flex-shrink-0 w-4 h-4 rounded-full border-2 border-green-brand/60 bg-green-brand/20" />
    );
  }
  return <span className="flex-shrink-0 w-4 h-4 rounded-full border border-border-default" />;
}

function CriterionRow({
  criterion,
  onChange,
  onRemove,
  onApprove,
}: {
  criterion: Criterion;
  onChange: (updated: Criterion) => void;
  onRemove: () => void;
  onApprove: () => void;
}) {
  const [open, setOpen] = useState(false);
  const [editingText, setEditingText] = useState(false);
  const [editingCmd, setEditingCmd] = useState(false);
  const [confirmRemove, setConfirmRemove] = useState(false);

  return (
    <li className="flex flex-col bg-surface rounded-lg border border-border-default overflow-hidden">
      <div className="flex items-center gap-2 px-3 py-2 group">
        <CriterionDot c={criterion} />
        {editingText ? (
          <input
            autoFocus
            className="flex-1 text-sm bg-transparent border-b border-green-brand focus:outline-none text-text-primary"
            value={criterion.text}
            onChange={(e) => onChange({ ...criterion, text: e.target.value })}
            onBlur={() => setEditingText(false)}
            onKeyDown={(e) => e.key === "Enter" && setEditingText(false)}
          />
        ) : (
          <span
            onClick={() => setEditingText(true)}
            className={`flex-1 text-sm cursor-text ${criterion.done ? "line-through text-text-muted" : "text-text-primary"}`}
          >
            {criterion.text}
          </span>
        )}
        <div className="flex items-center gap-1 flex-shrink-0">
          {confirmRemove ? (
            <>
              <span className="text-xs text-text-muted">Remove?</span>
              <button onClick={onRemove} className="text-xs text-red-brand hover:underline px-1">Yes</button>
              <button onClick={() => setConfirmRemove(false)} className="text-xs text-text-muted hover:text-text-primary px-1">Cancel</button>
            </>
          ) : (
            <button
              onClick={() => setConfirmRemove(true)}
              className="text-text-muted hover:text-red-brand text-xs px-1 opacity-0 group-hover:opacity-100 transition-opacity"
              aria-label="Remove criterion"
            >
              ✕
            </button>
          )}
          <button
            onClick={() => setOpen((v) => !v)}
            className="text-text-muted hover:text-text-primary p-0.5"
            aria-label={open ? "Collapse" : "Expand"}
          >
            <ChevronDown className={`w-3.5 h-3.5 transition-transform ${open ? "rotate-180" : ""}`} />
          </button>
        </div>
      </div>

      {open && (
        <div className="border-t border-border-default px-3 py-3 flex flex-col gap-3 bg-surface-2">
          <div>
            <span className="text-[10px] uppercase tracking-wide text-text-muted font-semibold">Test command</span>
            {editingCmd ? (
              <input
                autoFocus
                className="w-full text-xs font-mono bg-transparent border-b border-green-brand focus:outline-none text-text-primary mt-0.5"
                placeholder="e.g. pytest tests/test_x.py::test_y"
                value={criterion.test_cmd ?? ""}
                onChange={(e) => onChange({ ...criterion, test_cmd: e.target.value || null })}
                onBlur={() => setEditingCmd(false)}
                onKeyDown={(e) => e.key === "Enter" && setEditingCmd(false)}
              />
            ) : (
              <div onClick={() => setEditingCmd(true)} className="text-xs font-mono text-text-muted cursor-text mt-0.5">
                {criterion.test_cmd ?? <span className="italic opacity-50">click to add</span>}
              </div>
            )}
          </div>

          {criterion.file_path && (
            <div>
              <span className="text-[10px] uppercase tracking-wide text-text-muted font-semibold">File</span>
              <div className="text-xs font-mono text-text-primary mt-0.5 break-all">{criterion.file_path}</div>
            </div>
          )}

          {criterion.notes && (
            <div>
              <span className="text-[10px] uppercase tracking-wide text-text-muted font-semibold">Notes</span>
              <div className="text-xs text-text-primary mt-0.5">{criterion.notes}</div>
            </div>
          )}

          {criterion.evidence && (
            <div>
              <span className="text-[10px] uppercase tracking-wide text-text-muted font-semibold">Test output</span>
              <pre className="text-[10px] font-mono bg-surface rounded p-2 overflow-x-auto text-text-muted whitespace-pre-wrap mt-0.5">
                {criterion.evidence}
              </pre>
            </div>
          )}

          {criterion.done && !criterion.verified && (
            <div className="flex items-center gap-2 pt-1">
              <button
                onClick={onApprove}
                className="text-xs px-3 py-1.5 rounded-lg bg-green-brand text-white hover:bg-green-brand/90 transition-colors font-medium"
              >
                Approve
              </button>
              <span className="text-xs text-text-muted">Agent marked this done</span>
            </div>
          )}
        </div>
      )}
    </li>
  );
}

function PermissionPanel({ agentId, prompt, onDone }: { agentId: string; prompt: string; onDone: () => void }) {
  const [loading, setLoading] = useState<"allow" | "deny" | null>(null);

  async function respond(r: "y" | "n") {
    setLoading(r === "y" ? "allow" : "deny");
    try {
      await respondPermission(agentId, r);
      onDone();
    } finally {
      setLoading(null);
    }
  }

  return (
    <div className="flex flex-col gap-3 p-4 bg-amber-50 dark:bg-amber-950/30 border border-amber-200 dark:border-amber-800/50 rounded-xl">
      <div className="flex items-center gap-2">
        <span className="text-amber-600 dark:text-amber-400 text-sm font-semibold">Agent requesting permission</span>
      </div>
      <p className="text-sm text-[var(--text)] font-mono whitespace-pre-wrap">{prompt}</p>
      <div className="flex gap-2">
        <button
          onClick={() => respond("y")}
          disabled={!!loading}
          className="px-4 py-1.5 text-sm font-medium bg-[var(--green)] text-white rounded-lg hover:bg-[var(--green-2)] disabled:opacity-40 transition-colors"
        >
          {loading === "allow" ? "Allowing…" : "Allow"}
        </button>
        <button
          onClick={() => respond("n")}
          disabled={!!loading}
          className="px-4 py-1.5 text-sm font-medium border border-[var(--border)] text-[var(--text-2)] rounded-lg hover:text-[var(--text)] disabled:opacity-40 transition-colors"
        >
          {loading === "deny" ? "Denying…" : "Deny"}
        </button>
      </div>
    </div>
  );
}

export function TicketDetailClient() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const { workspaceId } = useWorkspace();
  const { mutate } = useSWRConfig();

  const { data: ticket, isLoading, error } = useTicket(id);
  const { data: events = [] } = useTicketEvents(id);
  const { data: agents = [] } = useAgents(workspaceId);
  const { data: traces = [] } = useTicketTraces(id);
  const { data: metrics = [] } = useTicketTelemetry(id);
  const { data: allTickets = [] } = useTickets(workspaceId);

  const [criteria, setCriteria] = useState<Criterion[] | null>(null);
  const [newText, setNewText] = useState("");
  const [saving, setSaving] = useState(false);
  const [refining, setRefining] = useState(false);

  const leftPane = useDragResize(260, 200, 420);
  const rightPane = useDragResize(360, 280, 560, true);

  const activeCriteria = (criteria ?? ticket?.acceptance_criteria ?? []).map(normalizeCriterion);

  if (isLoading) {
    return <div className="flex items-center justify-center h-64"><Spinner className="h-8 w-8" /></div>;
  }

  if (error) {
    const isNotFound = (error as Error).message?.includes("API 404");
    return isNotFound
      ? <EmptyState Icon={TicketIcon} title="Ticket not found" sub="This ticket may have been deleted." />
      : <EmptyTicketFetchError />;
  }

  if (!ticket) return null;

  const activeAgent = agents.find((a) => a.current_ticket_id === ticket.id);
  const dirty = criteria !== null;

  async function saveCriteria() {
    if (!criteria) return;
    setSaving(true);
    try {
      await updateTicketCriteria(id, criteria);
      setCriteria(null);
      mutate(["ticket", id]);
    } finally {
      setSaving(false);
    }
  }

  async function runRefine() {
    setRefining(true);
    try {
      const updated = await refineTicket(id);
      setCriteria(updated.acceptance_criteria);
      mutate(["ticket", id]);
    } finally {
      setRefining(false);
    }
  }

  async function approveCriterion(criterionId: string) {
    const updated = activeCriteria.map((c) =>
      c.id === criterionId ? { ...c, verified: true } : c
    );
    await updateTicketCriteria(id, updated);
    setCriteria(null);
    mutate(["ticket", id]);
  }

  function addCriterion() {
    if (!newText.trim()) return;
    setCriteria([...activeCriteria, { id: crypto.randomUUID(), text: newText.trim(), test_cmd: null, done: false, verified: false, evidence: null, file_path: null, notes: null }]);
    setNewText("");
  }

  return (
    <div className="flex h-full min-h-0 gap-2">
      {/* Left pane — ticket queue */}
      <aside
        className="hidden xl:flex flex-col min-h-0 flex-shrink-0 bg-[var(--surface)] border border-[var(--border)] rounded-xl overflow-y-auto divide-y divide-[var(--border)]"
        style={{ width: leftPane.width }}
      >
        {allTickets.map((t) => (
          <div key={t.id} className={t.id === id ? "bg-[var(--surface-2)]" : undefined}>
            <TicketRow ticket={t} />
          </div>
        ))}
      </aside>
      <PaneHandle onMouseDown={leftPane.onMouseDown} />

      {/* Center pane — ticket detail */}
      <main className="flex-1 min-w-0 overflow-y-auto">
        <div className="flex flex-col gap-6 max-w-3xl mx-auto">
      <div className="flex flex-col gap-2">
        <button
          type="button"
          onClick={() => (window.history.length > 1 ? router.back() : router.push("/tickets"))}
          className="text-text-muted hover:text-text-primary text-sm w-fit"
        >
          ← back
        </button>
        <div className="flex items-start justify-between gap-4">
          <h1 className="text-2xl font-bold text-text-primary">{ticket.title}</h1>
          <div className="flex items-center gap-2">
            {activeAgent && <AgentControls agent={activeAgent} />}
            <ImplementButton
              ticketId={id}
              active={!!activeAgent}
              onStarted={() => mutate(["agents", workspaceId])}
            />
          </div>
        </div>
        {ticket.description && (
          <p className="text-text-muted text-sm">{ticket.description}</p>
        )}
        <div className="flex items-center gap-2 flex-wrap">
          <Badge label={ticket.status} />
        </div>
      </div>

      {/* Criteria editor */}
      <div className="flex flex-col gap-3">
        <div className="flex items-center justify-between">
          <h2 className="text-sm font-semibold text-text-primary">
            Acceptance Criteria
            <span className="ml-2 text-text-muted font-normal text-xs">
              {activeCriteria.filter((c) => c.verified).length} verified · {activeCriteria.filter((c) => c.done && !c.verified).length} claimed · {activeCriteria.filter((c) => !c.done).length} open
            </span>
          </h2>
          <div className="flex items-center gap-2">
            <button
              onClick={runRefine}
              disabled={refining}
              className="text-xs px-2 py-1 rounded-lg border border-border-default text-text-muted hover:text-text-primary hover:border-green-brand/40 transition-colors disabled:opacity-40"
            >
              {refining ? "Refining…" : "✦ Refine with AI"}
            </button>
            {dirty && (
              <button
                onClick={saveCriteria}
                disabled={saving}
                className="text-xs px-3 py-1 rounded-lg bg-green-brand text-white hover:bg-green-brand/90 transition-colors disabled:opacity-40"
              >
                {saving ? "Saving…" : "Save"}
              </button>
            )}
          </div>
        </div>

        {activeCriteria.length > 0 && (
          <ul className="flex flex-col gap-1">
            {activeCriteria.map((c) => (
              <CriterionRow
                key={c.id}
                criterion={c}
                onChange={(updated) => setCriteria(activeCriteria.map((x) => x.id === updated.id ? updated : x))}
                onRemove={() => setCriteria(activeCriteria.filter((x) => x.id !== c.id))}
                onApprove={() => approveCriterion(c.id)}
              />
            ))}
          </ul>
        )}

        <div className="flex gap-2">
          <input
            type="text"
            value={newText}
            onChange={(e) => setNewText(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && addCriterion()}
            placeholder="Add a criterion…"
            className="flex-1 text-sm bg-surface border border-border-default rounded-lg px-3 py-2 text-text-primary placeholder-text-muted focus:outline-none focus:border-green-brand transition-colors"
          />
          <button
            onClick={addCriterion}
            className="px-3 py-2 text-sm border border-border-default rounded-lg text-text-muted hover:text-text-primary hover:border-green-brand/40 transition-colors"
          >
            Add
          </button>
        </div>
      </div>

      {(() => {
        const lastEvent = [...events].reverse().find((e) => e.event_type === "permission_requested" || e.event_type === "log" || e.event_type === "done" || e.event_type === "error");
        if (lastEvent?.event_type === "permission_requested" && activeAgent) {
          const payload = lastEvent.payload as { prompt?: string };
          return (
            <PermissionPanel
              agentId={activeAgent.id}
              prompt={payload.prompt ?? "Permission required"}
              onDone={() => mutate(["events", id])}
            />
          );
        }
        return null;
      })()}

      {/* Below xl the right-pane content stacks into the center column */}
      <div className="xl:hidden flex flex-col gap-6">
        <MetricsPanel metrics={metrics} />
        {traces.length > 0 && (
          <div style={{ height: 280 }}>
            <TraceTree traces={traces} />
          </div>
        )}
      </div>

      <div style={{ height: 400 }}>
        <TicketEventLog events={events} agents={agents} />
      </div>
        </div>
      </main>

      <PaneHandle onMouseDown={rightPane.onMouseDown} />

      {/* Right pane — telemetry + trace visualizer */}
      <aside
        className="hidden xl:flex flex-col gap-4 min-h-0 flex-shrink-0 overflow-y-auto"
        style={{ width: rightPane.width }}
      >
        <MetricsPanel metrics={metrics} />
        <div className="flex-1 min-h-0" style={{ minHeight: 240 }}>
          <TraceTree traces={traces} />
        </div>
      </aside>
    </div>
  );
}
