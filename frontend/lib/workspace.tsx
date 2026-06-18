"use client";

import React, { createContext, useContext, useEffect, useState } from "react";
import useSWR from "swr";
import { fetchWorkspaces } from "./api";
import type { Workspace } from "./types";

const STORAGE_KEY = "treco_workspace_id";

interface WorkspaceCtx {
  workspaceId: string;
  setWorkspaceId: (id: string) => void;
  workspaces: Workspace[];
}

const WorkspaceContext = createContext<WorkspaceCtx>({
  workspaceId: "",
  setWorkspaceId: () => {},
  workspaces: [],
});

const POLL = { refreshInterval: 30_000, revalidateOnFocus: false } as const;

export function useWorkspaces() {
  return useSWR("workspaces", fetchWorkspaces, POLL);
}

export function WorkspaceProvider({ children }: { children: React.ReactNode }) {
  const { data: workspaces = [] } = useWorkspaces();
  const [workspaceId, setWorkspaceIdState] = useState("");
  const [hydrated, setHydrated] = useState(false);

  useEffect(() => {
    const stored = localStorage.getItem(STORAGE_KEY);
    if (stored) setWorkspaceIdState(stored);
    setHydrated(true);
  }, []);

  useEffect(() => {
    if (!hydrated) return;
    if (workspaces.length === 0) {
      if (workspaceId) setWorkspaceIdState("");
      return;
    }
    const stillExists = workspaces.some((w) => w.id === workspaceId);
    if (!stillExists) {
      setWorkspaceIdState(workspaces[0].id);
      localStorage.setItem(STORAGE_KEY, workspaces[0].id);
    }
  }, [hydrated, workspaces, workspaceId]);

  function setWorkspaceId(id: string) {
    setWorkspaceIdState(id);
    localStorage.setItem(STORAGE_KEY, id);
  }

  return (
    <WorkspaceContext.Provider value={{ workspaceId, setWorkspaceId, workspaces }}>
      {children}
    </WorkspaceContext.Provider>
  );
}

export function useWorkspace() {
  return useContext(WorkspaceContext);
}
