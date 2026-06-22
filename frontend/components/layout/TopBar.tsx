"use client";

import { useWorkspace } from "@/lib/workspace";
import { useAgents } from "@/lib/hooks";
import { WorkspaceTabs } from "./WorkspaceTabs";

export function TopBar() {
  const { workspaceId } = useWorkspace();
  const { data: agents } = useAgents(workspaceId);

  const working = agents?.filter((a) => a.status === "working").length ?? 0;

  return (
    <header className="h-14 flex items-center justify-between px-6 border-b border-[var(--border)] bg-[var(--surface)] flex-shrink-0">
      <div className="flex items-center gap-3">
        {working > 0 && (
          <div
            aria-live="polite"
            aria-label={`${working} agent${working !== 1 ? "s" : ""} working`}
            className="flex items-center gap-1.5 text-xs bg-[var(--green-3)] border border-[var(--green)]/25 text-[var(--green-badge-text)] px-2.5 py-1 rounded-full font-medium"
          >
            <span aria-hidden="true" className="relative flex h-1.5 w-1.5">
              <span className="ping-slow absolute inline-flex h-full w-full rounded-full bg-[var(--green)] opacity-75" />
              <span className="relative inline-flex rounded-full h-1.5 w-1.5 bg-[var(--green)]" />
            </span>
            <span aria-hidden="true">{working} agent{working !== 1 ? "s" : ""} working</span>
          </div>
        )}
      </div>

      <div className="flex items-center gap-3">
        <WorkspaceTabs />
      </div>
    </header>
  );
}
