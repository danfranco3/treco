"use client";

import { useState, useEffect } from "react";
import { useSWRConfig } from "swr";
import { Check, Copy, Sun, Moon, Monitor, ExternalLink } from "lucide-react";
import { useWorkspace } from "@/lib/workspace";
import { updateWorkspace } from "@/lib/api";
import { Card } from "@/components/ui/Card";
import { useTheme } from "@/lib/theme";
import { cn } from "@/lib/utils";
import {
  type ImplSettings,
  DEFAULT_IMPL,
  loadImplSettings,
  saveImplSettings,
} from "@/lib/impl-settings";

const GITHUB_URL = "https://github.com/danfranco3/treco";

const THEME_OPTIONS = [
  { value: "light" as const, label: "Light", Icon: Sun },
  { value: "dark"  as const, label: "Dark",  Icon: Moon },
  { value: "system" as const, label: "System", Icon: Monitor },
];

export default function SettingsPage() {
  const { workspaceId, workspace } = useWorkspace();
  const { mutate } = useSWRConfig();
  const { theme, setTheme } = useTheme();

  const [name, setName] = useState(workspace?.name ?? "");
  const [repoPath, setRepoPath] = useState(workspace?.repo_path ?? "");
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState("");
  const [copied, setCopied] = useState(false);
  const [impl, setImpl] = useState<ImplSettings>(DEFAULT_IMPL);
  const [implSaved, setImplSaved] = useState(false);

  useEffect(() => {
    if (workspace?.name) setName(workspace.name);
    if (workspace?.repo_path != null) setRepoPath(workspace.repo_path);
    setImpl(loadImplSettings());
  }, [workspace?.name, workspace?.repo_path]);

  async function handleSave() {
    setSaving(true);
    setError("");
    try {
      await updateWorkspace(workspaceId, {
        name: name.trim() || undefined,
        repo_path: repoPath.trim() || undefined,
      });
      await mutate("workspaces");
      setSaved(true);
      setTimeout(() => setSaved(false), 2000);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to save");
    } finally {
      setSaving(false);
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
      <h1 className="text-xl font-bold text-[var(--text)]">Settings</h1>

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

      <Card className="flex flex-col gap-5">
        <h2 className="text-sm font-semibold text-[var(--text)]">Workspace</h2>

        <div className="flex flex-col gap-1.5">
          <label className="text-xs font-medium text-[var(--text-2)]" htmlFor="ws-name">Name</label>
          <input
            id="ws-name"
            type="text"
            value={name}
            onChange={(e) => setName(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && handleSave()}
            className="bg-[var(--surface)] border border-[var(--border)] rounded-lg px-3 py-2 text-sm text-[var(--text)] focus:outline-none focus:border-[var(--green)] transition-colors"
          />
        </div>

        <div className="flex flex-col gap-1.5">
          <label className="text-xs font-medium text-[var(--text-2)]" htmlFor="ws-repo">Repo Path</label>
          <input
            id="ws-repo"
            type="text"
            value={repoPath}
            onChange={(e) => setRepoPath(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && handleSave()}
            placeholder="/absolute/path/to/repo"
            className="bg-[var(--surface)] border border-[var(--border)] rounded-lg px-3 py-2 text-sm text-[var(--text)] font-mono placeholder-[var(--text-3)] focus:outline-none focus:border-[var(--green)] transition-colors"
          />
          <p className="text-xs text-[var(--text-3)]">Used to run verification test commands.</p>
        </div>

        <div className="flex flex-col gap-1.5">
          <label className="text-xs font-medium text-[var(--text-2)]">Workspace ID</label>
          <div className="flex items-center gap-2 bg-[var(--surface-2)] border border-[var(--border)] rounded-lg px-3 py-2">
            <code className="flex-1 text-xs font-mono text-[var(--text-2)] truncate">{workspaceId}</code>
            <button onClick={copyId} className="text-[var(--text-3)] hover:text-[var(--text-2)] transition-colors">
              {copied ? <Check className="w-3.5 h-3.5 text-[var(--green)]" /> : <Copy className="w-3.5 h-3.5" />}
            </button>
          </div>
          <p className="text-xs text-[var(--text-3)]">Pass to CLI: <code className="font-mono">TRECO_WORKSPACE_ID=…</code></p>
        </div>

        <div className="flex items-center gap-2">
          <button
            onClick={handleSave}
            disabled={saving}
            className="flex items-center gap-1.5 px-4 py-2 text-sm font-medium bg-[var(--green)] text-white rounded-lg hover:bg-[var(--green-2)] disabled:opacity-40 transition-colors"
          >
            {saved ? <Check className="w-3.5 h-3.5" /> : null}
            {saved ? "Saved" : saving ? "Saving…" : "Save"}
          </button>
          {error && <p className="text-xs text-red-600">{error}</p>}
        </div>

        <pre className="text-xs font-mono bg-stone-900 rounded-lg px-4 py-3 text-green-400 overflow-x-auto leading-5">{`pip install treco
TRECO_WORKSPACE_ID=${workspaceId || "<id>"} treco init
treco new`}</pre>
      </Card>

      <Card className="flex flex-col gap-5">
        <h2 className="text-sm font-semibold text-[var(--text)]">Implementation</h2>

        <div className="flex flex-col gap-1.5">
          <label className="text-xs font-medium text-[var(--text-2)]" htmlFor="impl-model">Model</label>
          <input
            id="impl-model"
            type="text"
            value={impl.model}
            onChange={(e) => setImpl((s) => ({ ...s, model: e.target.value }))}
            placeholder="claude-sonnet-5"
            className="bg-[var(--surface)] border border-[var(--border)] rounded-lg px-3 py-2 text-sm text-[var(--text)] font-mono placeholder-[var(--text-3)] focus:outline-none focus:border-[var(--green)] transition-colors"
          />
          <p className="text-xs text-[var(--text-3)]">Used for both Claude Code and Anthropic modes.</p>
        </div>

        <div className="flex flex-col gap-1.5">
          <label className="text-xs font-medium text-[var(--text-2)]" htmlFor="impl-prompt">System Prompt</label>
          <textarea
            id="impl-prompt"
            rows={4}
            value={impl.system_prompt}
            onChange={(e) => setImpl((s) => ({ ...s, system_prompt: e.target.value }))}
            placeholder="You are an expert software engineer..."
            className="bg-[var(--surface)] border border-[var(--border)] rounded-lg px-3 py-2 text-sm text-[var(--text)] placeholder-[var(--text-3)] focus:outline-none focus:border-[var(--green)] transition-colors resize-y"
          />
        </div>

        <label className="flex items-start gap-3 cursor-pointer group">
          <input
            type="checkbox"
            checked={impl.skip_permissions}
            onChange={(e) => setImpl((s) => ({ ...s, skip_permissions: e.target.checked }))}
            className="mt-0.5 accent-[var(--green)] w-4 h-4 cursor-pointer"
          />
          <span className="flex flex-col gap-0.5">
            <span className="text-sm font-medium text-[var(--text)]">Skip permissions (Claude Code)</span>
            <span className="text-xs text-[var(--text-3)]">
              Runs with <code className="font-mono">--dangerously-skip-permissions</code>. When unchecked, Claude Code
              will pause for approval on sensitive operations and you&apos;ll respond from the ticket page.
            </span>
          </span>
        </label>

        <div className="flex items-center gap-2">
          <button
            onClick={() => {
              saveImplSettings(impl);
              setImplSaved(true);
              setTimeout(() => setImplSaved(false), 2000);
            }}
            className="flex items-center gap-1.5 px-4 py-2 text-sm font-medium bg-[var(--green)] text-white rounded-lg hover:bg-[var(--green-2)] transition-colors"
          >
            {implSaved ? <Check className="w-3.5 h-3.5" /> : null}
            {implSaved ? "Saved" : "Save"}
          </button>
        </div>
      </Card>

      <div className="flex items-center gap-4 pt-2 border-t border-[var(--border)]">
        <span className="text-xs text-[var(--text-3)]">Treco v0.1.0 · AGPL v3</span>
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
