"use client";

import { useState } from "react";
import { useSWRConfig } from "swr";
import { assignTicket } from "@/lib/api";
import type { Agent } from "@/lib/types";

interface AssignAgentPanelProps {
  ticketId: string;
  idleAgents: Agent[];
}

export function AssignAgentPanel({ ticketId, idleAgents }: AssignAgentPanelProps) {
  const { mutate } = useSWRConfig();
  const [selected, setSelected] = useState(idleAgents[0]?.id ?? "");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [copied, setCopied] = useState(false);

  const launchCmd = `treco start ${ticketId}`;

  function copyCmd() {
    navigator.clipboard.writeText(launchCmd).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    });
  }

  async function handleAssign() {
    if (!selected) return;
    setLoading(true);
    setError("");
    try {
      await assignTicket(selected, ticketId);
      // Optimistically update agent + ticket state; SSE will confirm
      mutate(["ticket", ticketId]);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to assign agent");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="border border-border-default rounded-xl p-4 flex flex-col gap-3">
      <h3 className="text-xs font-semibold text-text-muted uppercase tracking-wide">
        No agent working this ticket
      </h3>

      {idleAgents.length > 0 ? (
        <>
          <div className="flex gap-2">
            <select
              value={selected}
              onChange={(e) => setSelected(e.target.value)}
              className="flex-1 bg-surface-2 border border-border-default rounded-lg px-2 py-1.5 text-sm text-text-primary outline-none focus:border-cyan-brand/60"
            >
              {idleAgents.map((a) => (
                <option key={a.id} value={a.id}>
                  {a.name}
                </option>
              ))}
            </select>
            <button
              onClick={handleAssign}
              disabled={loading || !selected}
              className="text-xs bg-cyan-brand/10 border border-cyan-brand/40 text-cyan-brand hover:bg-cyan-brand/20 px-3 py-1.5 rounded-lg disabled:opacity-40 transition-colors"
            >
              {loading ? "Assigning…" : "Assign"}
            </button>
          </div>
          {error && <p className="text-xs text-red-brand">{error}</p>}
        </>
      ) : (
        <p className="text-xs text-text-muted">No idle agents available.</p>
      )}

      <div className="border-t border-border-default pt-3 flex items-center gap-2">
        <code className="flex-1 text-xs font-mono text-text-muted truncate">{launchCmd}</code>
        <button
          onClick={copyCmd}
          className="text-xs border border-border-default hover:border-cyan-brand/40 text-text-muted hover:text-text-primary px-2 py-1 rounded transition-colors flex-shrink-0"
        >
          {copied ? "Copied!" : "Copy"}
        </button>
      </div>
    </div>
  );
}
