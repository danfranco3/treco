"use client";

import { useState } from "react";
import { ChevronDown } from "lucide-react";
import type { TraceNode } from "@/lib/types";
import { formatTime } from "@/lib/utils";

const STEP_LABEL: Record<string, { label: string; color: string }> = {
  llm_turn:        { label: "LLM",   color: "text-blue-500" },
  tool_call:       { label: "TOOL",  color: "text-green-brand" },
  test_run:        { label: "TEST",  color: "text-amber-brand" },
  criterion_check: { label: "CRIT",  color: "text-green-brand" },
  permission_gate: { label: "GATE",  color: "text-amber-400" },
};

const STATUS_DOT: Record<string, string> = {
  ok: "bg-green-brand",
  error: "bg-red-brand",
  running: "bg-blue-400 animate-pulse",
  skipped: "bg-text-muted",
};

function scrollToEvent(eventId: string) {
  const el = document.getElementById(`evt-${eventId}`);
  if (!el) return;
  el.scrollIntoView({ behavior: "smooth", block: "center" });
  el.classList.add("bg-amber-500/20");
  setTimeout(() => el.classList.remove("bg-amber-500/20"), 1500);
}

function TraceRow({ node, depth }: { node: TraceNode; depth: number }) {
  const [open, setOpen] = useState(true);
  const step = STEP_LABEL[node.step_type] ?? { label: node.step_type, color: "text-text-muted" };
  const tokens = node.tokens_in + node.tokens_out;

  return (
    <li>
      <div
        className={`flex items-center gap-2 py-1 px-2 rounded text-xs font-mono hover:bg-[var(--surface-2)] transition-colors ${node.event_id ? "cursor-pointer" : ""}`}
        style={{ paddingLeft: `${depth * 16 + 8}px` }}
        onClick={() => node.event_id && scrollToEvent(node.event_id)}
        title={node.event_id ? "Jump to event in log" : undefined}
      >
        {node.children.length > 0 ? (
          <button
            onClick={(e) => {
              e.stopPropagation();
              setOpen((v) => !v);
            }}
            className="text-text-muted hover:text-text-primary flex-shrink-0"
            aria-label={open ? "Collapse" : "Expand"}
          >
            <ChevronDown className={`w-3 h-3 transition-transform ${open ? "" : "-rotate-90"}`} />
          </button>
        ) : (
          <span className="w-3 flex-shrink-0" />
        )}
        <span className={`w-2 h-2 rounded-full flex-shrink-0 ${STATUS_DOT[node.status] ?? "bg-text-muted"}`} />
        <span className={`font-semibold flex-shrink-0 ${step.color}`}>[{step.label}]</span>
        {node.tool_name && <span className="text-text-primary truncate">{node.tool_name}</span>}
        {typeof node.payload.brief === "string" && node.payload.brief && (
          <span className="text-text-muted truncate">{node.payload.brief}</span>
        )}
        <span className="ml-auto flex items-center gap-2 flex-shrink-0 text-text-muted">
          {tokens > 0 && <span>{node.tokens_in}→{node.tokens_out} tok</span>}
          {node.duration_ms != null && <span>{node.duration_ms}ms</span>}
          <span className="opacity-60">{formatTime(node.created_at)}</span>
        </span>
      </div>
      {open && node.children.length > 0 && (
        <ul>
          {node.children.map((child) => (
            <TraceRow key={child.id} node={child} depth={depth + 1} />
          ))}
        </ul>
      )}
    </li>
  );
}

export function TraceTree({ traces }: { traces: TraceNode[] }) {
  return (
    <div className="flex flex-col h-full">
      <h3 className="text-xs font-semibold text-text-muted uppercase tracking-wider mb-2">
        Trace
      </h3>
      <div className="flex-1 min-h-0 overflow-y-auto bg-[var(--surface-2)] rounded-xl border border-[var(--border)] p-2">
        {traces.length === 0 ? (
          <p className="text-text-muted opacity-50 text-center text-xs py-8">no trace steps yet</p>
        ) : (
          <ul>
            {traces.map((node) => (
              <TraceRow key={node.id} node={node} depth={0} />
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}
