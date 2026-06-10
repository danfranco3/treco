"use client";

import { useState } from "react";

interface OnboardingCardProps {
  workspaceId: string;
}

const DISMISS_KEY = "treco_onboarding_dismissed";

export function OnboardingCard({ workspaceId }: OnboardingCardProps) {
  const [dismissed, setDismissed] = useState(() => {
    if (typeof window === "undefined") return false;
    return localStorage.getItem(DISMISS_KEY) === "1";
  });

  if (dismissed) return null;

  function dismiss() {
    localStorage.setItem(DISMISS_KEY, "1");
    setDismissed(true);
  }

  const serverUrl =
    typeof window !== "undefined"
      ? `${window.location.protocol}//${window.location.hostname}:8001`
      : "http://localhost:8001";

  const steps: { cmd: string; label: string }[] = [
    { label: "Install SDK", cmd: "pip install treco" },
    { label: "Connect to this server", cmd: `TRECO_URL=${serverUrl} treco init` },
    { label: "Import a ticket", cmd: "treco import <github-issue-url>" },
    { label: "Start tracking", cmd: "treco start" },
  ];

  return (
    <div className="border border-cyan-brand/30 bg-cyan-brand/5 rounded-xl p-6 relative">
      <button
        onClick={dismiss}
        className="absolute top-4 right-4 text-text-muted hover:text-text-primary text-xs"
        aria-label="Dismiss"
      >
        ✕
      </button>

      <h2 className="text-sm font-semibold text-text-primary mb-1">Get started with Treco</h2>
      <p className="text-xs text-text-muted mb-4">
        No agents or tickets yet. Run these commands to start tracking agent progress.
      </p>

      <ol className="flex flex-col gap-2">
        {steps.map((step, i) => (
          <li key={i} className="flex items-center gap-3">
            <span className="text-xs text-text-muted w-4 flex-shrink-0">{i + 1}.</span>
            <span className="text-xs text-text-muted w-36 flex-shrink-0">{step.label}</span>
            <code className="text-xs font-mono bg-surface-2 border border-border-default text-cyan-brand px-2 py-1 rounded select-all">
              {step.cmd}
            </code>
          </li>
        ))}
      </ol>

      <p className="text-xs text-text-muted mt-4">
        Claude Code users: run{" "}
        <code className="font-mono text-cyan-brand">treco hook install</code> to auto-track
        token usage from every tool call.
      </p>

      <p className="text-xs text-text-muted mt-2">
        Workspace:{" "}
        <code className="font-mono text-text-primary">{workspaceId}</code>
      </p>
    </div>
  );
}
