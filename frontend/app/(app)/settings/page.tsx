"use client";

import { useState, useEffect } from "react";
import { useSWRConfig } from "swr";
import { Settings, Trash2, Copy, Check, ExternalLink, Sun, Moon, Monitor } from "lucide-react";
import { useWorkspace } from "@/lib/workspace";
import { deleteWorkspace, updateWorkspace } from "@/lib/api";
import { Card } from "@/components/ui/Card";
import { useTheme } from "@/lib/theme";
import { cn } from "@/lib/utils";

const GITHUB_URL = "https://github.com/danfranco3/treco";

const THEME_OPTIONS = [
  { value: "light" as const, label: "Light", Icon: Sun },
  { value: "dark"  as const, label: "Dark",  Icon: Moon },
  { value: "system" as const, label: "System", Icon: Monitor },
];

export default function SettingsPage() {
  const { workspaceId, setWorkspaceId, workspaces } = useWorkspace();
  const { mutate } = useSWRConfig();
  const { theme, setTheme } = useTheme();
  const workspace = workspaces.find((w) => w.id === workspaceId);

  const [name, setName] = useState(workspace?.name ?? "");

  useEffect(() => {
    if (workspace?.name) setName(workspace.name);
  }, [workspace?.name]);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [saveError, setSaveError] = useState("");
  const [deleting, setDeleting] = useState(false);
  const [confirmDelete, setConfirmDelete] = useState(false);
  const [copied, setCopied] = useState(false);

  if (!workspace) {
    return (
      <div className="flex flex-col items-center justify-center h-64 gap-2">
        <Settings className="w-8 h-8 text-[var(--text-3)]" />
        <p className="text-sm text-[var(--text-2)]">Select a workspace to manage its settings.</p>
      </div>
    );
  }

  async function handleSave() {
    if (!name.trim() || name === workspace?.name) return;
    setSaving(true);
    setSaveError("");
    try {
      await updateWorkspace(workspaceId, { name: name.trim() });
      await mutate("workspaces");
      setSaved(true);
      setTimeout(() => setSaved(false), 2000);
    } catch (e) {
      setSaveError(e instanceof Error ? e.message : "Failed to save");
    } finally {
      setSaving(false);
    }
  }

  async function handleDelete() {
    setDeleting(true);
    try {
      await deleteWorkspace(workspaceId);
      await mutate("workspaces");
      const remaining = workspaces.filter((w) => w.id !== workspaceId);
      setWorkspaceId(remaining[0]?.id ?? "");
    } catch (e) {
      setSaveError(e instanceof Error ? e.message : "Failed to delete");
    } finally {
      setDeleting(false);
      setConfirmDelete(false);
    }
  }

  function copyId() {
    navigator.clipboard.writeText(workspaceId).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    });
  }

  return (
    <div className="flex flex-col gap-8 max-w-2xl">
      <div>
        <h1 className="text-xl font-bold text-[var(--text)]">Settings</h1>
        <p className="text-sm text-[var(--text-2)] mt-1">Manage workspace configuration.</p>
      </div>

      {/* Appearance */}
      <Card className="flex flex-col gap-4">
        <h2 className="text-sm font-semibold text-[var(--text)]">Appearance</h2>
        <div className="flex gap-2">
          {THEME_OPTIONS.map(({ value, label, Icon }) => (
            <button
              key={value}
              onClick={() => setTheme(value)}
              className={cn(
                "flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium border transition-colors",
                theme === value
                  ? "border-[var(--green)] bg-[var(--green-3)] text-[var(--green-badge-text)]"
                  : "border-[var(--border)] text-[var(--text-2)] hover:text-[var(--text)] hover:bg-[var(--surface-2)]",
              )}
            >
              <Icon className="w-3.5 h-3.5" />
              {label}
            </button>
          ))}
        </div>
      </Card>

      {/* Workspace */}
      <Card className="flex flex-col gap-5">
        <h2 className="text-sm font-semibold text-[var(--text)]">Workspace</h2>

        <div className="flex flex-col gap-1.5">
          <label className="text-xs font-medium text-[var(--text-2)]" htmlFor="ws-name">Name</label>
          <div className="flex gap-2">
            <input
              id="ws-name"
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && handleSave()}
              className="flex-1 bg-[var(--surface)] border border-[var(--border)] rounded-lg px-3 py-2 text-sm text-[var(--text)] focus:outline-none focus:border-[var(--green)] transition-colors"
            />
            <button
              onClick={handleSave}
              disabled={saving || !name.trim() || name === workspace.name}
              className="flex items-center gap-1.5 px-4 py-2 text-sm font-medium bg-[var(--green)] text-white rounded-lg hover:bg-[var(--green-2)] disabled:opacity-40 transition-colors"
            >
              {saved ? <Check className="w-3.5 h-3.5" /> : null}
              {saved ? "Saved" : saving ? "Saving…" : "Save"}
            </button>
          </div>
          {saveError && <p className="text-xs text-red-600">{saveError}</p>}
        </div>

        <div className="flex flex-col gap-1.5">
          <label className="text-xs font-medium text-[var(--text-2)]">Workspace ID</label>
          <div className="flex items-center gap-2 bg-[var(--surface-2)] border border-[var(--border)] rounded-lg px-3 py-2">
            <code className="flex-1 text-xs font-mono text-[var(--text-2)] truncate">{workspaceId}</code>
            <button
              onClick={copyId}
              className="flex items-center gap-1 text-xs text-[var(--text-3)] hover:text-[var(--text-2)] transition-colors"
            >
              {copied ? <Check className="w-3.5 h-3.5 text-[var(--green)]" /> : <Copy className="w-3.5 h-3.5" />}
            </button>
          </div>
          <p className="text-xs text-[var(--text-3)]">Pass this to the SDK: <code className="font-mono">TRECO_WORKSPACE_ID=…</code></p>
        </div>

        {workspace.repo_path && (
          <div className="flex flex-col gap-1.5">
            <label className="text-xs font-medium text-[var(--text-2)]">Repository</label>
            <div className="bg-[var(--surface-2)] border border-[var(--border)] rounded-lg px-3 py-2">
              <code className="text-xs font-mono text-[var(--text-2)]">{workspace.repo_path}</code>
            </div>
          </div>
        )}
      </Card>

      {/* SDK quick-start */}
      <Card className="flex flex-col gap-4">
        <h2 className="text-sm font-semibold text-[var(--text)]">Quick start</h2>
        <p className="text-xs text-[var(--text-2)]">Connect an agent to this workspace:</p>
        <pre className="text-xs font-mono bg-stone-900 rounded-lg px-4 py-3 text-green-400 overflow-x-auto leading-5">{`pip install treco
TRECO_WORKSPACE_ID=${workspaceId} treco init
treco start`}</pre>
      </Card>

      {/* Danger zone */}
      <div className="flex flex-col gap-3">
        <h2 className="text-sm font-semibold text-red-600">Danger zone</h2>
        <div className="border border-red-200 rounded-xl p-4 flex items-center justify-between gap-4">
          <div>
            <p className="text-sm font-medium text-[var(--text)]">Delete workspace</p>
            <p className="text-xs text-[var(--text-3)] mt-0.5">Permanently removes this workspace and all associated data.</p>
          </div>
          {!confirmDelete ? (
            <button
              onClick={() => setConfirmDelete(true)}
              className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium text-red-600 border border-red-200 rounded-lg hover:bg-red-50 transition-colors flex-shrink-0"
            >
              <Trash2 className="w-3.5 h-3.5" />
              Delete
            </button>
          ) : (
            <div className="flex items-center gap-2 flex-shrink-0">
              <span className="text-xs text-[var(--text-2)]">Sure?</span>
              <button
                onClick={handleDelete}
                disabled={deleting}
                className="px-3 py-1.5 text-xs font-medium text-white bg-red-600 rounded-lg hover:bg-red-700 disabled:opacity-50 transition-colors"
              >
                {deleting ? "Deleting…" : "Yes, delete"}
              </button>
              <button
                onClick={() => setConfirmDelete(false)}
                className="px-3 py-1.5 text-xs text-[var(--text-2)] hover:text-[var(--text)] transition-colors"
              >
                Cancel
              </button>
            </div>
          )}
        </div>
      </div>

      {/* About */}
      <div className="flex items-center gap-4 pt-2 border-t border-[var(--border)]">
        <div className="flex items-center gap-1.5 text-xs text-[var(--text-3)]">
          <span>Treco v0.1.0</span>
          <span>·</span>
          <span>MIT License</span>
        </div>
        <a
          href={GITHUB_URL}
          target="_blank"
          rel="noopener noreferrer"
          className="flex items-center gap-1 text-xs text-[var(--text-3)] hover:text-[var(--text)] transition-colors ml-auto"
        >
          <ExternalLink className="w-3 h-3" />
          GitHub
        </a>
      </div>
    </div>
  );
}
