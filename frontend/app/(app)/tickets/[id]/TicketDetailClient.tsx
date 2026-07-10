"use client";

import { useState, useRef, useEffect } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { useSWRConfig } from "swr";
import { useAgents, useTicket, useTicketEvents } from "@/lib/hooks";
import { useWorkspace } from "@/lib/workspace";
import { Badge } from "@/components/ui/Badge";
import { Spinner } from "@/components/ui/Spinner";
import { TicketEventLog } from "@/components/ticket-detail/TicketEventLog";
import { EmptyState, EmptyTicketFetchError } from "@/components/ui/EmptyState";
import { Ticket as TicketIcon, ChevronDown } from "lucide-react";
import { updateTicketCriteria, refineTicket, implementTicket } from "@/lib/api";
import { loadImplSettings } from "@/lib/impl-settings";
import type { Criterion } from "@/lib/types";

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
      await implementTicket(ticketId, { method, model: s.model, system_prompt: s.system_prompt });
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
        </div>
      )}

      {error && <p className="absolute top-full mt-1 right-0 text-xs text-red-500 whitespace-nowrap">{error}</p>}
    </div>
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

export function TicketDetailClient() {
  const { id } = useParams<{ id: string }>();
  const { workspaceId } = useWorkspace();
  const { mutate } = useSWRConfig();

  const { data: ticket, isLoading, error } = useTicket(id);
  const { data: events = [] } = useTicketEvents(id);
  const { data: agents = [] } = useAgents(workspaceId);

  const [criteria, setCriteria] = useState<Criterion[] | null>(null);
  const [newText, setNewText] = useState("");
  const [saving, setSaving] = useState(false);
  const [refining, setRefining] = useState(false);

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
    <div className="flex flex-col gap-6 max-w-3xl mx-auto">
      <div className="flex flex-col gap-2">
        <Link href="/tickets" className="text-text-muted hover:text-text-primary text-sm w-fit">← back</Link>
        <div className="flex items-start justify-between gap-4">
          <h1 className="text-2xl font-bold text-text-primary">{ticket.title}</h1>
          <ImplementButton
            ticketId={id}
            active={!!activeAgent}
            onStarted={() => mutate(["agents", workspaceId])}
          />
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

      <div style={{ height: 400 }}>
        <TicketEventLog events={events} agents={agents} />
      </div>
    </div>
  );
}
