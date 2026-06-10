"use client";

import { useWorkspace } from "./workspace";
import { useAgentStream, useWorkspaceStream } from "./hooks";

export function StreamProvider({ children }: { children: React.ReactNode }) {
  const { workspaceId } = useWorkspace();
  useWorkspaceStream(workspaceId);
  useAgentStream(workspaceId);
  return <>{children}</>;
}
