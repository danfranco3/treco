"use client";

import { Leaf } from "lucide-react";

const BACKEND = process.env.NEXT_PUBLIC_BACKEND_URL ?? "http://localhost:8001";

function GitHubIcon() {
  return (
    <svg viewBox="0 0 24 24" width="18" height="18" fill="currentColor" aria-hidden="true">
      <path d="M12 0C5.37 0 0 5.37 0 12c0 5.31 3.435 9.795 8.205 11.385.6.105.825-.255.825-.57 0-.285-.015-1.23-.015-2.235-3.015.555-3.795-.735-4.035-1.41-.135-.345-.72-1.41-1.23-1.695-.42-.225-1.02-.78-.015-.795.945-.015 1.62.87 1.845 1.23 1.08 1.815 2.805 1.305 3.495.99.105-.78.42-1.305.765-1.605-2.67-.3-5.46-1.335-5.46-5.925 0-1.305.465-2.385 1.23-3.225-.12-.3-.54-1.53.12-3.18 0 0 1.005-.315 3.3 1.23.96-.27 1.98-.405 3-.405s2.04.135 3 .405c2.295-1.56 3.3-1.23 3.3-1.23.66 1.65.24 2.88.12 3.18.765.84 1.23 1.905 1.23 3.225 0 4.605-2.805 5.625-5.475 5.925.435.375.81 1.095.81 2.22 0 1.605-.015 2.895-.015 3.3 0 .315.225.69.825.57A12.02 12.02 0 0 0 24 12c0-6.63-5.37-12-12-12Z" />
    </svg>
  );
}

export default function LoginPage() {
  return (
    <div className="min-h-screen bg-[var(--bg)] flex items-center justify-center px-4">
      <div className="w-full max-w-sm">
        <div className="flex flex-col items-center gap-6 text-center mb-8">
          <div className="w-12 h-12 rounded-2xl bg-[var(--green)] flex items-center justify-center">
            <Leaf className="w-6 h-6 text-white" />
          </div>
          <div>
            <h1 className="text-2xl font-bold tracking-tight text-[var(--text)]">Sign in to Treco</h1>
            <p className="text-sm text-[var(--text-2)] mt-1">Real-time observability for AI agents</p>
          </div>
        </div>

        <div className="bg-[var(--surface)] border border-[var(--border)] rounded-xl p-6 shadow-card">
          <a
            href={`${BACKEND}/api/auth/github`}
            className="flex w-full items-center justify-center gap-3 rounded-lg border border-[var(--border)] bg-[var(--bg)] px-4 py-2.5 text-sm font-medium text-[var(--text)] hover:bg-[var(--surface-2)] transition-colors"
          >
            <GitHubIcon />
            Continue with GitHub
          </a>
          <p className="mt-4 text-center text-xs text-[var(--text-3)]">
            Open source · Self-hosted · MIT licensed
          </p>
        </div>
      </div>
    </div>
  );
}
