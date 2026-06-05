"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { cn } from "@/lib/utils";

const NAV = [
  { href: "/dashboard", label: "Dashboard",   icon: "⬡" },
  { href: "/tickets",   label: "Tickets",     icon: "◈" },
  { href: "/agents",    label: "Agents",      icon: "◎" },
];

export function Sidebar() {
  const path = usePathname();

  return (
    <aside className="w-56 flex-shrink-0 flex flex-col bg-surface border-r border-border-default">
      <div className="px-5 py-5 border-b border-border-default">
        <div className="flex items-center gap-2">
          <span className="text-cyan-brand text-xl font-mono font-bold">⬡</span>
          <span className="text-text-primary font-bold tracking-tight text-lg">Treco</span>
        </div>
        <p className="text-text-muted text-xs mt-1">agent observability</p>
      </div>

      <nav className="flex-1 px-3 py-4 space-y-1">
        {NAV.map((item) => {
          const active = path.startsWith(item.href);
          return (
            <Link
              key={item.href}
              href={item.href}
              className={cn(
                "flex items-center gap-3 px-3 py-2 rounded-lg text-sm transition-colors",
                active
                  ? "bg-surface-2 text-cyan-brand font-medium"
                  : "text-text-muted hover:text-text-primary hover:bg-surface-2"
              )}
            >
              <span className="text-base w-5 text-center">{item.icon}</span>
              {item.label}
            </Link>
          );
        })}
      </nav>

      <div className="px-5 py-4 border-t border-border-default">
        <p className="text-text-muted text-xs">v0.1.0 · open source</p>
      </div>
    </aside>
  );
}
