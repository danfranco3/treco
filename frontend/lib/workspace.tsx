"use client";

import React, { createContext, useContext, useEffect, useState } from "react";

const DEFAULT_ID = process.env.NEXT_PUBLIC_WORKSPACE_ID ?? "demo";
const STORAGE_KEY = "treco_workspace_id";

interface WorkspaceCtx {
  workspaceId: string;
  setWorkspaceId: (id: string) => void;
}

const WorkspaceContext = createContext<WorkspaceCtx>({
  workspaceId: DEFAULT_ID,
  setWorkspaceId: () => {},
});

export function WorkspaceProvider({ children }: { children: React.ReactNode }) {
  const [workspaceId, setWorkspaceIdState] = useState(DEFAULT_ID);

  useEffect(() => {
    const stored = localStorage.getItem(STORAGE_KEY);
    if (stored) setWorkspaceIdState(stored);
  }, []);

  function setWorkspaceId(id: string) {
    setWorkspaceIdState(id);
    localStorage.setItem(STORAGE_KEY, id);
  }

  return (
    <WorkspaceContext.Provider value={{ workspaceId, setWorkspaceId }}>
      {children}
    </WorkspaceContext.Provider>
  );
}

export function useWorkspace() {
  return useContext(WorkspaceContext);
}
