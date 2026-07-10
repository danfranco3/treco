"use client";

import React, { createContext, useContext } from "react";
import useSWR from "swr";
import { fetchWorkspaces } from "./api";
import type { Workspace } from "./types";

interface WorkspaceCtx {
  workspaceId: string;
  workspace: Workspace | null;
}

const WorkspaceContext = createContext<WorkspaceCtx>({ workspaceId: "", workspace: null });

const POLL = { refreshInterval: 30_000, revalidateOnFocus: false } as const;

export function WorkspaceProvider({ children }: { children: React.ReactNode }) {
  const { data: workspaces = [] } = useSWR("workspaces", fetchWorkspaces, POLL);
  const workspace = workspaces[0] ?? null;

  return (
    <WorkspaceContext.Provider value={{ workspaceId: workspace?.id ?? "", workspace }}>
      {children}
    </WorkspaceContext.Provider>
  );
}

export function useWorkspace() {
  return useContext(WorkspaceContext);
}
