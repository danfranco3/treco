"use client";

import { useEffect, useState } from "react";
import { browseFs } from "@/lib/api";

interface FolderBrowserProps {
  onSelect: (path: string) => void;
}

export function FolderBrowser({ onSelect }: FolderBrowserProps) {
  const [currentPath, setCurrentPath] = useState<string | undefined>(undefined);
  const [entries, setEntries] = useState<{ name: string; path: string; is_git_repo: boolean }[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    setLoading(true);
    setError("");
    browseFs(currentPath)
      .then((res) => {
        setCurrentPath(res.path);
        setEntries(res.entries);
      })
      .catch((e) => setError(e instanceof Error ? e.message : "Failed to browse"))
      .finally(() => setLoading(false));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  function navigate(path: string) {
    setLoading(true);
    setError("");
    browseFs(path)
      .then((res) => {
        setCurrentPath(res.path);
        setEntries(res.entries);
      })
      .catch((e) => setError(e instanceof Error ? e.message : "Failed to browse"))
      .finally(() => setLoading(false));
  }

  function goUp() {
    if (!currentPath) return;
    const parent = currentPath.split("/").slice(0, -1).join("/") || "/";
    navigate(parent);
  }

  return (
    <div className="flex flex-col gap-2 border border-border-default rounded-lg p-3 bg-surface-2">
      <div className="flex items-center justify-between gap-2">
        <code className="text-xs text-text-muted truncate">{currentPath ?? "…"}</code>
        <button
          type="button"
          onClick={goUp}
          className="text-xs text-text-muted hover:text-text-primary flex-shrink-0"
        >
          ↑ up
        </button>
      </div>

      {error && <p className="text-xs text-red-brand">{error}</p>}

      <div className="flex flex-col max-h-48 overflow-y-auto">
        {loading ? (
          <p className="text-xs text-text-muted py-2">Loading…</p>
        ) : entries.length === 0 ? (
          <p className="text-xs text-text-muted py-2">No subdirectories</p>
        ) : (
          entries.map((entry) => (
            <button
              key={entry.path}
              type="button"
              onClick={() => navigate(entry.path)}
              className="text-left text-xs px-2 py-1.5 rounded hover:bg-surface text-text-primary flex items-center gap-2"
            >
              <span>{entry.is_git_repo ? "◈" : "▸"}</span>
              {entry.name}
              {entry.is_git_repo && <span className="text-green-brand text-[10px]">git</span>}
            </button>
          ))
        )}
      </div>

      <button
        type="button"
        onClick={() => currentPath && onSelect(currentPath)}
        disabled={!currentPath}
        className="text-xs bg-green-brand/10 border border-green-brand/40 text-green-brand hover:bg-green-brand/20 px-3 py-1.5 rounded-lg disabled:opacity-40 transition-colors"
      >
        Use this folder
      </button>
    </div>
  );
}
