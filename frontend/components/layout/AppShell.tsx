"use client";

import { useState, useCallback } from "react";
import { useRouter } from "next/navigation";
import { Sidebar } from "./Sidebar";
import { TopBar } from "./TopBar";
import { ShortcutsModal } from "@/components/ui/ShortcutsModal";
import { useKeyboardShortcuts } from "@/lib/useKeyboardShortcuts";

export function AppShell({ children }: { children: React.ReactNode }) {
  const [collapsed, setCollapsed] = useState(false);
  const [shortcutsOpen, setShortcutsOpen] = useState(false);
  const router = useRouter();

  const onShowShortcuts = useCallback(() => setShortcutsOpen(true), []);
  const onNewTicket = useCallback(() => router.push("/tickets/new"), [router]);

  useKeyboardShortcuts({ onShowShortcuts, onNewTicket });

  return (
    <div className="flex h-screen overflow-hidden">
      <Sidebar collapsed={collapsed} onToggle={() => setCollapsed((v) => !v)} />
      <div className="flex flex-col flex-1 min-w-0">
        <TopBar />
        <main id="main-content" className="flex-1 overflow-y-auto p-6">{children}</main>
      </div>
      <ShortcutsModal open={shortcutsOpen} onClose={() => setShortcutsOpen(false)} />
    </div>
  );
}
