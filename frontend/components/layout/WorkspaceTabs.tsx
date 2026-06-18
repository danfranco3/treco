"use client";

import { useState } from "react";
import { useWorkspace } from "@/lib/workspace";
import { useAgents } from "@/lib/hooks";
import type { Workspace } from "@/lib/types";
import { NewWorkspaceModal } from "./NewWorkspaceModal";

function WorkspaceTab({ workspace, active, onClick }: { workspace: Workspace; active: boolean; onClick: () => void }) {
  const { data: agents } = useAgents(workspace.id);
  const working = agents?.filter((a) => a.status === "working").length ?? 0;

  return (
    <button
      onClick={onClick}
      className={`flex items-center gap-2 px-3 py-1.5 rounded-lg text-xs border transition-colors ${
        active
          ? "bg-cyan-brand/10 border-cyan-brand/40 text-cyan-brand"
          : "border-border-default text-text-muted hover:text-text-primary hover:border-gray-500"
      }`}
    >
      {workspace.name}
      {working > 0 && (
        <span className="flex items-center justify-center min-w-[1.1rem] h-[1.1rem] px-1 rounded-full bg-cyan-brand/20 text-cyan-brand text-[10px] font-semibold">
          {working}
        </span>
      )}
    </button>
  );
}

export function WorkspaceTabs() {
  const { workspaceId, setWorkspaceId, workspaces } = useWorkspace();
  const [modalOpen, setModalOpen] = useState(false);

  return (
    <div className="flex items-center gap-2">
      {workspaces.map((w) => (
        <WorkspaceTab
          key={w.id}
          workspace={w}
          active={w.id === workspaceId}
          onClick={() => setWorkspaceId(w.id)}
        />
      ))}
      <button
        onClick={() => setModalOpen(true)}
        aria-label="New workspace"
        className="flex items-center justify-center w-7 h-7 rounded-lg text-sm border border-border-default text-text-muted hover:text-text-primary hover:border-gray-500 transition-colors"
      >
        +
      </button>
      {modalOpen && <NewWorkspaceModal onClose={() => setModalOpen(false)} />}
    </div>
  );
}
