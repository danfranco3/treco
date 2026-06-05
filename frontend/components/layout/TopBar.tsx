"use client";

import { useWorkspace } from "@/lib/workspace";
import { useAgents } from "@/lib/hooks";

export function TopBar() {
  const { workspaceId, setWorkspaceId } = useWorkspace();
  const { data: agents } = useAgents(workspaceId);

  const working = agents?.filter((a) => a.status === "working").length ?? 0;

  return (
    <header className="h-14 flex items-center justify-between px-6 border-b border-border-default bg-surface flex-shrink-0">
      <div className="flex items-center gap-3">
        {working > 0 && (
          <div className="flex items-center gap-2 text-xs bg-cyan-brand/10 border border-cyan-brand/30 text-cyan-brand px-3 py-1 rounded-full">
            <span className="relative flex h-2 w-2">
              <span className="ping-slow absolute inline-flex h-full w-full rounded-full bg-cyan-brand opacity-75" />
              <span className="relative inline-flex rounded-full h-2 w-2 bg-cyan-brand" />
            </span>
            {working} agent{working !== 1 ? "s" : ""} working
          </div>
        )}
      </div>

      <div className="flex items-center gap-2">
        <span className="text-text-muted text-xs">workspace</span>
        <input
          type="text"
          value={workspaceId}
          onChange={(e) => setWorkspaceId(e.target.value)}
          className="bg-surface-2 border border-border-default rounded px-2 py-1 text-xs text-text-primary w-32 focus:outline-none focus:border-cyan-brand/50"
        />
      </div>
    </header>
  );
}
