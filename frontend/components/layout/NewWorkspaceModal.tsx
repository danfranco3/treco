"use client";

import { useState } from "react";
import { useSWRConfig } from "swr";
import { createWorkspace } from "@/lib/api";
import { useWorkspace } from "@/lib/workspace";
import { FolderBrowser } from "./FolderBrowser";

interface NewWorkspaceModalProps {
  onClose: () => void;
}

export function NewWorkspaceModal({ onClose }: NewWorkspaceModalProps) {
  const { mutate } = useSWRConfig();
  const { setWorkspaceId } = useWorkspace();
  const [name, setName] = useState("");
  const [repoPath, setRepoPath] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  async function handleSubmit() {
    if (!name.trim() || !repoPath.trim()) return;
    setLoading(true);
    setError("");
    try {
      const workspace = await createWorkspace({ name: name.trim(), repo_path: repoPath.trim() });
      await mutate("workspaces");
      setWorkspaceId(workspace.id);
      onClose();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to create workspace");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4">
      <div className="bg-surface border border-border-default rounded-xl p-5 w-full max-w-lg flex flex-col gap-4">
        <h2 className="text-sm font-semibold text-text-primary">New workspace</h2>

        <div className="flex flex-col gap-1">
          <label className="text-xs text-text-muted">Name</label>
          <input
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="my-project"
            className="bg-surface-2 border border-border-default rounded-lg px-2 py-1.5 text-sm text-text-primary outline-none focus:border-green-brand/60"
          />
        </div>

        <div className="flex flex-col gap-1">
          <label className="text-xs text-text-muted">Repo path</label>
          {repoPath ? (
            <div className="flex items-center justify-between gap-2 bg-surface-2 border border-border-default rounded-lg px-2 py-1.5">
              <code className="text-xs text-text-primary truncate">{repoPath}</code>
              <button
                type="button"
                onClick={() => setRepoPath("")}
                className="text-xs text-text-muted hover:text-text-primary flex-shrink-0"
              >
                change
              </button>
            </div>
          ) : (
            <FolderBrowser onSelect={setRepoPath} />
          )}
        </div>

        {error && <p className="text-xs text-red-brand">{error}</p>}

        <div className="flex justify-end gap-2">
          <button
            onClick={onClose}
            className="text-xs border border-border-default text-text-muted hover:text-text-primary px-3 py-1.5 rounded-lg transition-colors"
          >
            Cancel
          </button>
          <button
            onClick={handleSubmit}
            disabled={loading || !name.trim() || !repoPath.trim()}
            className="text-xs bg-green-brand/10 border border-green-brand/40 text-green-brand hover:bg-green-brand/20 px-3 py-1.5 rounded-lg disabled:opacity-40 transition-colors"
          >
            {loading ? "Creating…" : "Create workspace"}
          </button>
        </div>
      </div>
    </div>
  );
}
