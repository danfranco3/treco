"use client";

import { cn } from "@/lib/utils";

const SOURCES = ["all", "jira", "linear", "github", "asana", "custom"];
const STATUSES = ["all", "open", "in_progress", "done"];

interface TicketFilterProps {
  source: string;
  status: string;
  onSource: (s: string) => void;
  onStatus: (s: string) => void;
}

function Chip({ label, active, onClick }: { label: string; active: boolean; onClick: () => void }) {
  return (
    <button
      onClick={onClick}
      className={cn(
        "px-3 py-1 rounded-full text-xs border transition-colors",
        active
          ? "bg-cyan-brand/10 border-cyan-brand/40 text-cyan-brand"
          : "border-border-default text-text-muted hover:text-text-primary hover:border-gray-600"
      )}
    >
      {label}
    </button>
  );
}

export function TicketFilter({ source, status, onSource, onStatus }: TicketFilterProps) {
  return (
    <div className="flex items-center gap-6 flex-wrap">
      <div className="flex items-center gap-2">
        <span className="text-xs text-text-muted">source</span>
        <div className="flex gap-1">
          {SOURCES.map((s) => (
            <Chip key={s} label={s} active={source === s} onClick={() => onSource(s)} />
          ))}
        </div>
      </div>
      <div className="flex items-center gap-2">
        <span className="text-xs text-text-muted">status</span>
        <div className="flex gap-1">
          {STATUSES.map((s) => (
            <Chip key={s} label={s} active={status === s} onClick={() => onStatus(s)} />
          ))}
        </div>
      </div>
    </div>
  );
}
