"use client";

import { useRouter } from "next/navigation";
import useSWR from "swr";
import { LogOut } from "lucide-react";
import { useWorkspace } from "@/lib/workspace";
import { useAgents } from "@/lib/hooks";
import { fetchCurrentUser } from "@/lib/api";
import { clearToken } from "@/lib/auth";
import { WorkspaceTabs } from "./WorkspaceTabs";

export function TopBar() {
  const router = useRouter();
  const { workspaceId } = useWorkspace();
  const { data: agents } = useAgents(workspaceId);
  const { data: user } = useSWR("current-user", fetchCurrentUser, {
    revalidateOnFocus: false,
    onError: () => {
      clearToken();
      router.replace("/login");
    },
  });

  const working = agents?.filter((a) => a.status === "working").length ?? 0;

  function handleLogout() {
    clearToken();
    router.replace("/login");
  }

  return (
    <header className="h-14 flex items-center justify-between px-6 border-b border-[var(--border)] bg-white flex-shrink-0">
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
        {user && (
          <div className="flex items-center gap-2 pl-3 border-l border-[var(--border)]">
            {user.avatar_url ? (
              <img
                src={user.avatar_url}
                alt={user.login}
                className="w-7 h-7 rounded-full border border-[var(--border)]"
              />
            ) : (
              <div aria-hidden="true" className="w-7 h-7 rounded-full bg-[var(--green-3)] flex items-center justify-center text-xs font-medium text-[var(--green-badge-text)]">
                {user.login[0].toUpperCase()}
              </div>
            )}
            <span className="text-sm text-[var(--text-2)] hidden sm:block">{user.login}</span>
            <button
              onClick={handleLogout}
              aria-label="Sign out"
              className="p-1.5 rounded-md text-[var(--text-3)] hover:text-[var(--text)] hover:bg-[var(--surface-2)] transition-colors"
            >
              <LogOut aria-hidden="true" className="w-4 h-4" />
            </button>
          </div>
        )}
      </div>
    </header>
  );
}
