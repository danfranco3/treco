"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useState } from "react";
import { cn } from "@/lib/utils";

const NAV = [
  { href: "/dashboard", label: "Dashboard", icon: "⬡" },
  { href: "/tickets",   label: "Tickets",   icon: "◈" },
  { href: "/agents",    label: "Agents",    icon: "◎" },
];

export function Sidebar() {
  const path = usePathname();
  const [open, setOpen] = useState(false);

  return (
    <>
      {/* Mobile hamburger */}
      <button
        onClick={() => setOpen((v) => !v)}
        className="lg:hidden fixed top-4 left-4 z-[var(--z-sticky)] p-2 rounded-lg bg-[var(--surface)] border border-[var(--border)] text-[var(--text-2)] hover:text-[var(--text)]"
        aria-label="Toggle sidebar"
      >
        <span className="font-mono text-base">{open ? "✕" : "≡"}</span>
      </button>

      {/* Backdrop on mobile */}
      {open && (
        <div
          onClick={() => setOpen(false)}
          className="lg:hidden fixed inset-0 bg-[var(--bg)]/60 backdrop-blur-sm"
          style={{ zIndex: "var(--z-modal-bg)" }}
        />
      )}

      {/* Sidebar */}
      <aside className={cn(
        "flex-shrink-0 flex flex-col bg-[var(--surface)] border-r border-[var(--border)]",
        "transition-all duration-200",
        /* desktop: always visible, icon-only below 1024px */
        "hidden lg:flex lg:w-56",
        /* mobile: slide in as overlay */
        open && "flex fixed inset-y-0 left-0 w-56",
      )}
        style={{ zIndex: open ? "var(--z-modal)" : undefined }}
      >
        <div className="px-5 py-5 border-b border-[var(--border)]">
          <div className="flex items-center gap-2">
            <span className="text-[var(--cyan)] text-xl font-mono font-bold">⬡</span>
            <span className="text-[var(--text)] font-bold tracking-tight text-lg">Treco</span>
          </div>
          <p className="text-[var(--text-3)] text-xs mt-1">agent observability</p>
        </div>

        <nav className="flex-1 px-3 py-4 space-y-1">
          {NAV.map((item) => {
            const active = path.startsWith(item.href);
            return (
              <Link
                key={item.href}
                href={item.href}
                onClick={() => setOpen(false)}
                className={cn(
                  "flex items-center gap-3 px-3 py-2 rounded-lg text-sm transition-colors duration-150",
                  active
                    ? "bg-[var(--surface-2)] text-[var(--cyan)] font-medium"
                    : "text-[var(--text-2)] hover:text-[var(--text)] hover:bg-[var(--surface-2)]",
                )}
              >
                <span className="text-base w-5 text-center">{item.icon}</span>
                {item.label}
              </Link>
            );
          })}
        </nav>

        <div className="px-5 py-4 border-t border-[var(--border)]">
          <p className="text-[var(--text-3)] text-xs">v0.1.0 · open source</p>
          <p className="text-[var(--text-3)] text-xs mt-0.5 font-mono">⌘K to search</p>
        </div>
      </aside>
    </>
  );
}
