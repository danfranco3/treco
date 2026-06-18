"use client";

import { useState } from "react";
import Link from "next/link";
import { useWorkspace } from "@/lib/workspace";
import { fetchGitHubIssues, fetchLinearIssues, importTicket } from "@/lib/api";
import type { Ticket } from "@/lib/types";
import { Card } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";
import { Spinner } from "@/components/ui/Spinner";

type ImportSource = "github" | "linear" | "paste";

function GitHubIcon({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 24 24" fill="currentColor" className={className} aria-hidden>
      <path d="M12 2C6.477 2 2 6.484 2 12.017c0 4.425 2.865 8.18 6.839 9.504.5.092.682-.217.682-.483 0-.237-.008-.868-.013-1.703-2.782.605-3.369-1.343-3.369-1.343-.454-1.158-1.11-1.466-1.11-1.466-.908-.62.069-.608.069-.608 1.003.07 1.531 1.032 1.531 1.032.892 1.53 2.341 1.088 2.91.832.092-.647.35-1.088.636-1.338-2.22-.253-4.555-1.113-4.555-4.951 0-1.093.39-1.988 1.029-2.688-.103-.253-.446-1.272.098-2.65 0 0 .84-.27 2.75 1.026A9.564 9.564 0 0112 6.844a9.59 9.59 0 012.504.337c1.909-1.296 2.747-1.027 2.747-1.027.546 1.379.202 2.398.1 2.651.64.7 1.028 1.595 1.028 2.688 0 3.848-2.339 4.695-4.566 4.943.359.309.678.92.678 1.855 0 1.338-.012 2.419-.012 2.747 0 .268.18.58.688.482A10.019 10.019 0 0022 12.017C22 6.484 17.522 2 12 2z" />
    </svg>
  );
}

function LinearIcon({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 100 100" fill="currentColor" className={className} aria-hidden>
      <path d="M73.0 27.5L26.0 74.5C28.5 77.2 31.3 79.7 34.3 81.8L79.8 36.3C77.7 33.2 75.5 30.2 73.0 27.5Z" />
      <path d="M62.0 18.0L16.5 63.5C17.4 67.2 18.8 70.7 20.6 74.0L66.0 28.6C64.8 25.0 63.5 21.5 62.0 18.0Z" />
      <path d="M18.0 38.0C18.0 38.0 18.0 38.0 18.0 38.0C16.7 41.2 15.7 44.5 15.0 48.0L52.0 11.0C48.5 11.7 45.2 12.7 42.0 14.0L18.0 38.0Z" />
      <path d="M83.0 44.0L56.0 71.0C59.0 70.0 61.9 68.7 64.7 67.1L67.0 64.8C69.1 61.5 70.7 58.0 71.8 54.3L83.0 44.0Z" />
      <path d="M82.6 56.5L59.5 79.6C63.4 77.9 67.0 75.6 70.2 72.8L80.0 63.0C81.1 60.9 82.0 58.8 82.6 56.5Z" />
    </svg>
  );
}

function LinkIcon({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className={className} aria-hidden>
      <path d="M10 13a5 5 0 007.54.54l3-3a5 5 0 00-7.07-7.07l-1.72 1.71" />
      <path d="M14 11a5 5 0 00-7.54-.54l-3 3a5 5 0 007.07 7.07l1.71-1.71" />
    </svg>
  );
}

function JiraIcon({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 24 24" fill="currentColor" className={className} aria-hidden>
      <path d="M11.571 11.513H0a5.218 5.218 0 005.232 5.215h2.13v2.057A5.215 5.215 0 0012.575 24V12.518a1.005 1.005 0 00-1.004-1.005z" />
      <path d="M6.009 6.009H6.0a5.218 5.218 0 005.214 5.215h2.131v2.056a5.215 5.215 0 005.213 5.216V7.014a1.005 1.005 0 00-1.004-1.005z" opacity=".65" />
      <path d="M.448.448H.44a5.218 5.218 0 005.214 5.215h2.131v2.056A5.215 5.215 0 0012.998 12.934V1.453A1.005 1.005 0 0011.994.448z" opacity=".35" />
    </svg>
  );
}

function AsanaIcon({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 24 24" fill="currentColor" className={className} aria-hidden>
      <path d="M19.15 14.4c-2.69 0-4.87 2.18-4.87 4.87S16.46 24 19.15 24s4.87-2.18 4.87-4.87-2.18-4.73-4.87-4.73zm-14.3 0C2.16 14.4 0 16.58 0 19.27 0 21.96 2.16 24 4.85 24s4.87-2.18 4.87-4.87-2.16-4.73-4.87-4.73zM12 9.6c-2.69 0-4.87 2.18-4.87 4.87S9.31 19.34 12 19.34s4.87-2.18 4.87-4.87S14.69 9.6 12 9.6z" />
    </svg>
  );
}

interface SourceCard {
  value: ImportSource;
  label: string;
  description: string;
  icon: ({ className }: { className?: string }) => JSX.Element;
}

const SOURCES: SourceCard[] = [
  { value: "github", label: "GitHub Issues", description: "Import via Personal Access Token", icon: GitHubIcon },
  { value: "linear", label: "Linear", description: "Import via API key", icon: LinearIcon },
  { value: "paste", label: "Paste URL", description: "Paste any issue URL", icon: LinkIcon },
];

const COMING_SOON = [
  { label: "Jira", description: "Import via API token + domain", icon: JiraIcon },
  { label: "Asana", description: "Import via Personal Access Token", icon: AsanaIcon },
];

const STEP_LABELS = ["Choose source", "Connect", "Select & import"] as const;

interface FetchedIssue {
  ticket: Ticket;
  selected: boolean;
}

type Step = 1 | 2 | 3;

function ChevronLeftIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="w-4 h-4" aria-hidden>
      <polyline points="15 18 9 12 15 6" />
    </svg>
  );
}

function CheckIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" className="w-3.5 h-3.5" aria-hidden>
      <polyline points="20 6 9 17 4 12" />
    </svg>
  );
}

export default function ImportPage() {
  const { workspaceId } = useWorkspace();

  const [step, setStep] = useState<Step>(1);
  const [source, setSource] = useState<ImportSource | null>(null);

  const [ghToken, setGhToken] = useState("");
  const [ghRepo, setGhRepo] = useState("");

  const [linearKey, setLinearKey] = useState("");
  const [linearTeam, setLinearTeam] = useState("");

  const [pasteUrl, setPasteUrl] = useState("");

  const [fetchError, setFetchError] = useState("");
  const [fetching, setFetching] = useState(false);

  const [issues, setIssues] = useState<FetchedIssue[]>([]);
  const [importing, setImporting] = useState(false);
  const [importProgress, setImportProgress] = useState(0);
  const [importedCount, setImportedCount] = useState<number | null>(null);
  const [importError, setImportError] = useState("");

  function selectSource(s: ImportSource) {
    setSource(s);
    setStep(2);
    setFetchError("");
  }

  async function handleFetch() {
    if (!source) return;
    if (!workspaceId) {
      setFetchError("No workspace selected. Create a workspace before importing tickets.");
      return;
    }
    setFetchError("");
    setFetching(true);

    try {
      let tickets: Ticket[] = [];

      if (source === "github") {
        if (!ghToken.trim() || !ghRepo.trim()) {
          setFetchError("Token and repository are required");
          setFetching(false);
          return;
        }
        tickets = await fetchGitHubIssues(workspaceId, ghRepo.trim(), ghToken.trim());
      } else if (source === "linear") {
        if (!linearKey.trim()) {
          setFetchError("API key is required");
          setFetching(false);
          return;
        }
        tickets = await fetchLinearIssues(workspaceId, linearTeam.trim(), linearKey.trim());
      } else if (source === "paste") {
        if (!pasteUrl.trim()) {
          setFetchError("URL is required");
          setFetching(false);
          return;
        }
        const res = await fetch("/api/tickets/fetch/url", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ workspace_id: workspaceId, url: pasteUrl.trim() }),
        });
        if (!res.ok) throw new Error(`API ${res.status}: ${await res.text()}`);
        const ticket = await res.json() as Ticket;
        tickets = [ticket];
      }

      setIssues(tickets.map((t) => ({ ticket: t, selected: true })));
      setStep(3);
    } catch (err) {
      setFetchError(err instanceof Error ? err.message : "Failed to fetch issues");
    } finally {
      setFetching(false);
    }
  }

  function toggleIssue(index: number) {
    setIssues((prev) =>
      prev.map((item, i) =>
        i === index ? { ...item, selected: !item.selected } : item
      )
    );
  }

  function toggleAll() {
    const allSelected = issues.every((i) => i.selected);
    setIssues((prev) => prev.map((item) => ({ ...item, selected: !allSelected })));
  }

  async function handleImport() {
    const selected = issues.filter((i) => i.selected);
    if (selected.length === 0) return;
    if (!workspaceId) {
      setImportError("No workspace selected.");
      return;
    }

    setImporting(true);
    setImportError("");
    setImportProgress(0);

    let done = 0;
    try {
      for (const item of selected) {
        await importTicket({
          workspace_id: workspaceId,
          source: item.ticket.source as "jira" | "linear" | "asana" | "github",
          raw: item.ticket.body,
        });
        done++;
        setImportProgress(Math.round((done / selected.length) * 100));
      }
      setImportedCount(done);
    } catch (err) {
      setImportError(err instanceof Error ? err.message : "Import failed");
    } finally {
      setImporting(false);
    }
  }

  const selectedCount = issues.filter((i) => i.selected).length;
  const activeSource = SOURCES.find((s) => s.value === source);

  return (
    <div className="flex flex-col gap-6 max-w-2xl mx-auto">
      {/* Header */}
      <div className="flex items-center gap-3">
        <button
          type="button"
          onClick={() => {
            if (step > 1) setStep((step - 1) as Step);
          }}
          className="flex items-center gap-1 text-[var(--text-2)] hover:text-[var(--text)] transition-colors text-sm rounded-md px-1.5 py-1 hover:bg-[var(--surface-2)] -ml-1.5"
        >
          <ChevronLeftIcon />
          Back
        </button>
        <h1 className="text-xl font-semibold text-[var(--text)]">Import Tickets</h1>
      </div>

      {/* Step indicator */}
      <div className="flex items-center">
        {([1, 2, 3] as Step[]).map((s) => (
          <div key={s} className="flex items-center">
            <div className="flex items-center gap-2.5">
              <div
                className={`w-6 h-6 rounded-full flex items-center justify-center text-xs font-semibold shrink-0 transition-colors duration-200 ${
                  step === s
                    ? "bg-[var(--green)] text-[var(--bg)]"
                    : step > s
                    ? "bg-[var(--green)]/20 border border-[var(--green)] text-[var(--green)]"
                    : "border border-[var(--border)] text-[var(--text-3)]"
                }`}
              >
                {step > s ? <CheckIcon /> : s}
              </div>
              <span
                className={`text-sm whitespace-nowrap transition-colors duration-200 ${
                  step === s
                    ? "text-[var(--text)] font-medium"
                    : step > s
                    ? "text-[var(--text-2)]"
                    : "text-[var(--text-3)]"
                }`}
              >
                {STEP_LABELS[s - 1]}
              </span>
            </div>
            {s < 3 && (
              <div
                className={`mx-3 h-px flex-1 min-w-[32px] transition-colors duration-200 ${
                  step > s ? "bg-[var(--green)]/40" : "bg-[var(--border)]"
                }`}
              />
            )}
          </div>
        ))}
      </div>

      {/* Step 1: Choose source */}
      {step === 1 && (
        <div className="grid grid-cols-2 gap-3">
          {SOURCES.map((s) => {
            const Icon = s.icon;
            return (
              <button
                key={s.value}
                type="button"
                onClick={() => selectSource(s.value)}
                className="flex flex-col gap-3 p-4 bg-[var(--surface)] border border-[var(--border)] rounded-xl text-left hover:border-[var(--green)] hover:bg-[var(--surface-2)] transition-all duration-150 group"
              >
                <span className="text-[var(--green)] w-8 h-8 flex items-center justify-center rounded-lg bg-[var(--green)]/10 group-hover:bg-[var(--green)]/15 transition-colors">
                  <Icon className="w-4.5 h-4.5" />
                </span>
                <div className="flex flex-col gap-0.5">
                  <p className="font-medium text-[var(--text)] text-sm">{s.label}</p>
                  <p className="text-xs text-[var(--text-2)]">{s.description}</p>
                </div>
              </button>
            );
          })}
          {COMING_SOON.map((s) => {
            const Icon = s.icon;
            return (
              <div
                key={s.label}
                className="flex flex-col gap-3 p-4 bg-[var(--surface)] border border-[var(--border)] rounded-xl text-left opacity-40 cursor-not-allowed"
              >
                <span className="text-[var(--text-3)] w-8 h-8 flex items-center justify-center rounded-lg bg-[var(--surface-2)]">
                  <Icon className="w-4.5 h-4.5" />
                </span>
                <div className="flex flex-col gap-0.5">
                  <div className="flex items-center gap-2">
                    <p className="font-medium text-[var(--text)] text-sm">{s.label}</p>
                    <span className="text-[10px] font-medium text-[var(--text-3)] bg-[var(--surface-2)] px-1.5 py-0.5 rounded uppercase tracking-wide">Soon</span>
                  </div>
                  <p className="text-xs text-[var(--text-2)]">{s.description}</p>
                </div>
              </div>
            );
          })}
        </div>
      )}

      {/* Step 2: Connect */}
      {step === 2 && source && activeSource && (
        <Card className="flex flex-col gap-5">
          {/* Source context header */}
          <div className="flex items-center gap-2.5 pb-4 border-b border-[var(--border)]">
            <span className="text-[var(--green)] w-7 h-7 flex items-center justify-center rounded-md bg-[var(--green)]/10">
              <activeSource.icon className="w-4 h-4" />
            </span>
            <div>
              <p className="text-sm font-medium text-[var(--text)]">{activeSource.label}</p>
              <p className="text-xs text-[var(--text-2)]">{activeSource.description}</p>
            </div>
          </div>

          {source === "github" && (
            <>
              <div className="flex flex-col gap-1.5">
                <label className="text-xs font-medium text-[var(--text-2)] uppercase tracking-wide" htmlFor="gh-token">
                  Personal Access Token
                </label>
                <input
                  id="gh-token"
                  type="password"
                  value={ghToken}
                  onChange={(e) => setGhToken(e.target.value)}
                  placeholder="ghp_…"
                  className="bg-[var(--bg)] border border-[var(--border)] rounded-lg px-3 py-2.5 text-sm text-[var(--text)] placeholder:text-[var(--text-3)] focus:outline-none focus:border-[var(--green)] transition-colors font-mono"
                />
              </div>
              <div className="flex flex-col gap-1.5">
                <label className="text-xs font-medium text-[var(--text-2)] uppercase tracking-wide" htmlFor="gh-repo">
                  Repository
                </label>
                <input
                  id="gh-repo"
                  type="text"
                  value={ghRepo}
                  onChange={(e) => setGhRepo(e.target.value)}
                  placeholder="owner/repo"
                  className="bg-[var(--bg)] border border-[var(--border)] rounded-lg px-3 py-2.5 text-sm text-[var(--text)] placeholder:text-[var(--text-3)] focus:outline-none focus:border-[var(--green)] transition-colors font-mono"
                />
              </div>
            </>
          )}

          {source === "linear" && (
            <>
              <div className="flex flex-col gap-1.5">
                <label className="text-xs font-medium text-[var(--text-2)] uppercase tracking-wide" htmlFor="linear-key">
                  API Key
                </label>
                <input
                  id="linear-key"
                  type="password"
                  value={linearKey}
                  onChange={(e) => setLinearKey(e.target.value)}
                  placeholder="lin_api_…"
                  className="bg-[var(--bg)] border border-[var(--border)] rounded-lg px-3 py-2.5 text-sm text-[var(--text)] placeholder:text-[var(--text-3)] focus:outline-none focus:border-[var(--green)] transition-colors font-mono"
                />
              </div>
              <div className="flex flex-col gap-1.5">
                <label className="text-xs font-medium text-[var(--text-2)] uppercase tracking-wide" htmlFor="linear-team">
                  Team Key
                  <span className="ml-1 normal-case text-[var(--text-3)] font-normal">(optional)</span>
                </label>
                <input
                  id="linear-team"
                  type="text"
                  value={linearTeam}
                  onChange={(e) => setLinearTeam(e.target.value)}
                  placeholder="ENG"
                  className="bg-[var(--bg)] border border-[var(--border)] rounded-lg px-3 py-2.5 text-sm text-[var(--text)] placeholder:text-[var(--text-3)] focus:outline-none focus:border-[var(--green)] transition-colors font-mono"
                />
              </div>
            </>
          )}

          {source === "paste" && (
            <div className="flex flex-col gap-1.5">
              <label className="text-xs font-medium text-[var(--text-2)] uppercase tracking-wide" htmlFor="paste-url">
                Issue URL
              </label>
              <textarea
                id="paste-url"
                value={pasteUrl}
                onChange={(e) => setPasteUrl(e.target.value)}
                placeholder="https://github.com/owner/repo/issues/123"
                rows={3}
                className="bg-[var(--bg)] border border-[var(--border)] rounded-lg px-3 py-2.5 text-sm text-[var(--text)] placeholder:text-[var(--text-3)] focus:outline-none focus:border-[var(--green)] transition-colors resize-none font-mono"
              />
            </div>
          )}

          {fetchError && (
            <p className="text-sm text-[var(--red)] bg-[var(--red)]/10 border border-[var(--red)]/20 rounded-lg px-3 py-2">
              {fetchError}
            </p>
          )}

          <button
            type="button"
            onClick={handleFetch}
            disabled={fetching}
            className="flex items-center justify-center gap-2 px-5 py-2.5 bg-[var(--green)] text-[var(--bg)] text-sm font-semibold rounded-lg hover:opacity-90 transition-opacity disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {fetching && <Spinner className="border-[var(--bg)] border-r-transparent" />}
            {fetching ? "Fetching…" : "Fetch Issues"}
          </button>
        </Card>
      )}

      {/* Step 3: Select & import */}
      {step === 3 && (
        <div className="flex flex-col gap-4">
          {importedCount !== null ? (
            <Card className="flex flex-col items-center gap-4 py-10">
              <div className="w-12 h-12 rounded-full bg-[var(--green)]/15 border border-[var(--green)]/30 flex items-center justify-center">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" className="w-5 h-5 text-[var(--green)]" aria-hidden>
                  <polyline points="20 6 9 17 4 12" />
                </svg>
              </div>
              <div className="text-center">
                <p className="text-base font-semibold text-[var(--text)]">
                  {importedCount} ticket{importedCount !== 1 ? "s" : ""} imported
                </p>
                <p className="text-sm text-[var(--text-2)] mt-0.5">Ready to assign to agents</p>
              </div>
              <Link
                href="/tickets"
                className="px-5 py-2 bg-[var(--green)] text-[var(--bg)] text-sm font-semibold rounded-lg hover:opacity-90 transition-opacity"
              >
                View tickets
              </Link>
            </Card>
          ) : (
            <>
              <div className="flex items-center justify-between">
                <p className="text-sm text-[var(--text-2)]">
                  {issues.length} issue{issues.length !== 1 ? "s" : ""} found
                </p>
                <button
                  type="button"
                  onClick={toggleAll}
                  className="text-xs text-[var(--green)] hover:underline"
                >
                  {issues.every((i) => i.selected) ? "Deselect all" : "Select all"}
                </button>
              </div>

              <Card className="p-0 overflow-hidden">
                <ul className="divide-y divide-[var(--border)]">
                  {issues.map((item, index) => (
                    <li
                      key={item.ticket.id}
                      className="flex items-center gap-3 px-4 py-3 hover:bg-[var(--surface-2)] transition-colors"
                    >
                      <input
                        type="checkbox"
                        checked={item.selected}
                        onChange={() => toggleIssue(index)}
                        className="w-4 h-4 accent-[var(--green)] flex-shrink-0"
                        id={`issue-${index}`}
                      />
                      <label
                        htmlFor={`issue-${index}`}
                        className="flex-1 flex items-center gap-3 cursor-pointer min-w-0"
                      >
                        {item.ticket.source_id && (
                          <span className="text-xs text-[var(--text-3)] font-mono flex-shrink-0">
                            #{item.ticket.source_id}
                          </span>
                        )}
                        <span className="text-sm text-[var(--text)] truncate">
                          {item.ticket.title}
                        </span>
                      </label>
                      <Badge label={item.ticket.status} />
                    </li>
                  ))}
                </ul>
              </Card>

              {importing && (
                <div className="flex flex-col gap-1.5">
                  <div className="flex justify-between text-xs text-[var(--text-2)]">
                    <span>Importing…</span>
                    <span>{importProgress}%</span>
                  </div>
                  <div className="h-1 bg-[var(--surface-2)] rounded-full overflow-hidden">
                    <div
                      className="h-full bg-[var(--green)] transition-all duration-300"
                      style={{ width: `${importProgress}%` }}
                    />
                  </div>
                </div>
              )}

              {importError && (
                <p className="text-sm text-[var(--red)] bg-[var(--red)]/10 border border-[var(--red)]/20 rounded-lg px-3 py-2">
                  {importError}
                </p>
              )}

              <button
                type="button"
                onClick={handleImport}
                disabled={importing || selectedCount === 0}
                className="flex items-center justify-center gap-2 px-5 py-2.5 bg-[var(--green)] text-[var(--bg)] text-sm font-semibold rounded-lg hover:opacity-90 transition-opacity disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {importing && <Spinner className="border-[var(--bg)] border-r-transparent" />}
                {importing
                  ? "Importing…"
                  : `Import ${selectedCount} ticket${selectedCount !== 1 ? "s" : ""}`}
              </button>
            </>
          )}
        </div>
      )}
    </div>
  );
}
