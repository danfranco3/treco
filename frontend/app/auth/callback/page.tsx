"use client";

import { useRouter, useSearchParams } from "next/navigation";
import { useEffect, useState, Suspense } from "react";
import { setToken } from "@/lib/auth";

function CallbackHandler() {
  const router = useRouter();
  const params = useSearchParams();
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const token = params.get("token");
    if (!token) {
      setError("No token received from GitHub. Please try again.");
      return;
    }
    setToken(token);
    router.replace("/dashboard");
  }, [params, router]);

  if (error) {
    return (
      <div className="min-h-screen bg-[var(--bg)] flex items-center justify-center px-4">
        <div className="text-center">
          <p className="text-[var(--text)] font-medium mb-2">Authentication failed</p>
          <p className="text-sm text-[var(--text-2)] mb-6">{error}</p>
          <a
            href="/login"
            className="text-sm text-[var(--green)] hover:underline"
          >
            Back to login
          </a>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-[var(--bg)] flex items-center justify-center">
      <div className="flex flex-col items-center gap-3">
        <div className="w-8 h-8 rounded-full border-2 border-[var(--green)] border-t-transparent animate-spin" />
        <p className="text-sm text-[var(--text-2)]">Signing you in…</p>
      </div>
    </div>
  );
}

export default function AuthCallbackPage() {
  return (
    <Suspense>
      <CallbackHandler />
    </Suspense>
  );
}
