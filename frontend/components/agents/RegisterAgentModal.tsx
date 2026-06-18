"use client";

import { useState } from "react";
import { createAgent } from "@/lib/api";

interface RegisterAgentModalProps {
  workspaceId: string;
  onClose: () => void;
  onCreated: () => void;
}

type Step = "form" | "key";

export function RegisterAgentModal({ workspaceId, onClose, onCreated }: RegisterAgentModalProps) {
  const [step, setStep] = useState<Step>("form");
  const [name, setName] = useState("");
  const [apiKey, setApiKey] = useState("");
  const [agentId, setAgentId] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [copied, setCopied] = useState<"key" | "cmd" | null>(null);

  async function handleRegister() {
    if (!name.trim()) return;
    setLoading(true);
    setError("");
    try {
      const agent = await createAgent({ workspace_id: workspaceId, name: name.trim() });
      setApiKey(agent.api_key);
      setAgentId(agent.id);
      setStep("key");
      onCreated();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to create agent");
    } finally {
      setLoading(false);
    }
  }

  function copy(text: string, which: "key" | "cmd") {
    navigator.clipboard.writeText(text).then(() => {
      setCopied(which);
      setTimeout(() => setCopied(null), 2000);
    });
  }

  const launchCmd = `TRECO_API_KEY=${apiKey} treco start`;

  return (
    <div
      className="fixed inset-0 bg-black/60 flex items-center justify-center z-50"
      onClick={(e) => e.target === e.currentTarget && onClose()}
    >
      <div className="bg-surface border border-border-default rounded-xl p-6 w-full max-w-md shadow-xl">
        {step === "form" ? (
          <>
            <h2 className="text-base font-semibold text-text-primary mb-4">Register Agent</h2>

            <label className="block text-xs text-text-muted mb-1">Name</label>
            <input
              autoFocus
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && handleRegister()}
              placeholder="e.g. claude-dev-1"
              className="w-full bg-surface-2 border border-border-default rounded-lg px-3 py-2 text-sm text-text-primary placeholder:text-text-muted outline-none focus:border-green-brand/60 mb-4"
            />

            {error && <p className="text-xs text-red-brand mb-3">{error}</p>}

            <div className="flex gap-2 justify-end">
              <button
                onClick={onClose}
                className="text-xs text-text-muted hover:text-text-primary px-3 py-2"
              >
                Cancel
              </button>
              <button
                onClick={handleRegister}
                disabled={loading || !name.trim()}
                className="text-xs bg-green-brand/10 border border-green-brand/40 text-green-brand hover:bg-green-brand/20 px-4 py-2 rounded-lg disabled:opacity-40 transition-colors"
              >
                {loading ? "Creating…" : "Register"}
              </button>
            </div>
          </>
        ) : (
          <>
            <h2 className="text-base font-semibold text-text-primary mb-1">Agent registered</h2>
            <p className="text-xs text-text-muted mb-4">
              Save this API key — it will not be shown again.
            </p>

            <label className="block text-xs text-text-muted mb-1">API Key</label>
            <div className="flex gap-2 mb-4">
              <code className="flex-1 text-xs font-mono bg-surface-2 border border-border-default text-green-brand px-3 py-2 rounded-lg truncate select-all">
                {apiKey}
              </code>
              <button
                onClick={() => copy(apiKey, "key")}
                className="text-xs border border-border-default hover:border-green-brand/40 text-text-muted hover:text-text-primary px-3 py-2 rounded-lg transition-colors"
              >
                {copied === "key" ? "Copied!" : "Copy"}
              </button>
            </div>

            <label className="block text-xs text-text-muted mb-1">Launch command</label>
            <div className="flex gap-2 mb-6">
              <code className="flex-1 text-xs font-mono bg-surface-2 border border-border-default text-text-primary px-3 py-2 rounded-lg truncate select-all">
                {launchCmd}
              </code>
              <button
                onClick={() => copy(launchCmd, "cmd")}
                className="text-xs border border-border-default hover:border-green-brand/40 text-text-muted hover:text-text-primary px-3 py-2 rounded-lg transition-colors"
              >
                {copied === "cmd" ? "Copied!" : "Copy"}
              </button>
            </div>

            <div className="flex justify-end">
              <button
                onClick={onClose}
                className="text-xs bg-green-brand/10 border border-green-brand/40 text-green-brand hover:bg-green-brand/20 px-4 py-2 rounded-lg transition-colors"
              >
                Done
              </button>
            </div>
          </>
        )}
      </div>
    </div>
  );
}
