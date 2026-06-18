"use client";

import { useState } from "react";
import { useSWRConfig } from "swr";
import { implementTicket } from "@/lib/api";
import { buildDefaultPrompt } from "@/lib/utils";
import type { Ticket, Workspace } from "@/lib/types";

interface ImplementModalProps {
  ticket: Ticket;
  workspace: Workspace | null;
  workspaceId: string;
  onClose: () => void;
}

export function ImplementModal({ ticket, workspace, workspaceId, onClose }: ImplementModalProps) {
  const { mutate } = useSWRConfig();
  const [prompt, setPrompt] = useState(() => buildDefaultPrompt(ticket));
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const noWorkspace = !ticket.workspace_id;
  const noRepo = workspace && !workspace.repo_path;
  const blocked = noWorkspace || noRepo;

  async function handleSubmit() {
    if (!prompt.trim() || blocked) return;
    setLoading(true);
    setError("");
    try {
      await implementTicket(ticket.id, { prompt });
      mutate(["ticket", ticket.id]);
      mutate(["agents", workspaceId]);
      onClose();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to start agent");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4">
      <div className="bg-surface border border-border-default rounded-xl p-5 w-full max-w-2xl flex flex-col gap-4">
        <h2 className="text-sm font-semibold text-text-primary">Implement: {ticket.title}</h2>

        <div className="flex flex-col gap-1">
          <label className="text-xs text-text-muted">Workspace / repo</label>
          {noWorkspace ? (
            <p className="text-xs text-amber-400">No workspace assigned — assign one first from the ticket list.</p>
          ) : noRepo ? (
            <p className="text-xs text-amber-400">
              Workspace <span className="font-mono">{workspace?.name}</span> has no repo path. Edit it or pick a different workspace.
            </p>
          ) : (
            <div className="bg-surface-2 border border-border-default rounded-lg px-2 py-1.5">
              <span className="text-xs text-text-muted">{workspace?.name} · </span>
              <code className="text-xs text-text-primary">{workspace?.repo_path}</code>
            </div>
          )}
        </div>

        <div className="flex flex-col gap-1">
          <label className="text-xs text-text-muted">Initial prompt (editable)</label>
          <textarea
            value={prompt}
            onChange={(e) => setPrompt(e.target.value)}
            rows={10}
            disabled={!!blocked}
            className="bg-surface-2 border border-border-default rounded-lg px-2 py-1.5 text-sm text-text-primary font-mono outline-none focus:border-green-brand/60 resize-y disabled:opacity-40"
          />
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
            disabled={loading || !!blocked}
            className="text-xs bg-green-brand/10 border border-green-brand/40 text-green-brand hover:bg-green-brand/20 px-3 py-1.5 rounded-lg disabled:opacity-40 transition-colors"
          >
            {loading ? "Starting…" : "Implement"}
          </button>
        </div>
      </div>
    </div>
  );
}
