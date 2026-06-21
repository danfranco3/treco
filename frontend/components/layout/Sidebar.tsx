"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useState } from "react";
import { LayoutDashboard, Ticket, Bot, Settings, ChevronLeft, ChevronRight, Menu, X, Leaf } from "lucide-react";
import { cn } from "@/lib/utils";

const NAV = [
  { href: "/dashboard", label: "Dashboard", Icon: LayoutDashboard },
  { href: "/tickets",   label: "Tickets",   Icon: Ticket },
  { href: "/agents",    label: "Agents",    Icon: Bot },
];

const NAV_BOTTOM = [
  { href: "/settings",  label: "Settings",  Icon: Settings },
];

interface SidebarProps {
  collapsed?: boolean;
  onToggle?: () => void;
}

export function Sidebar({ collapsed = false, onToggle }: SidebarProps) {
  const path = usePathname();
  const [mobileOpen, setMobileOpen] = useState(false);

  return (
    <>
      {/* Mobile hamburger */}
      <button
        onClick={() => setMobileOpen((v) => !v)}
        aria-expanded={mobileOpen}
        aria-controls="sidebar"
        aria-label={mobileOpen ? "Close sidebar" : "Open sidebar"}
        className="lg:hidden fixed top-4 left-4 z-[var(--z-sticky)] p-2 rounded-lg bg-white border border-[var(--border)] text-[var(--text-2)] hover:text-[var(--text)] shadow-card"
      >
        {mobileOpen ? <X className="w-4 h-4" aria-hidden="true" /> : <Menu className="w-4 h-4" aria-hidden="true" />}
      </button>

      {/* Mobile backdrop */}
      {mobileOpen && (
        <button
          type="button"
          aria-label="Close sidebar"
          onClick={() => setMobileOpen(false)}
          onKeyDown={(e) => e.key === "Escape" && setMobileOpen(false)}
          className="lg:hidden fixed inset-0 bg-stone-900/20 backdrop-blur-sm cursor-default"
          style={{ zIndex: "var(--z-modal-bg)" }}
          tabIndex={-1}
        />
      )}

      {/* Sidebar */}
      <aside
        id="sidebar"
        aria-label="Application sidebar"
        className={cn(
          "flex-shrink-0 flex flex-col bg-white border-r border-[var(--border)]",
          "transition-all duration-200 ease-in-out",
          "hidden lg:flex",
          collapsed ? "lg:w-14" : "lg:w-56",
          mobileOpen && "flex fixed inset-y-0 left-0 w-56",
        )}
        style={{ zIndex: mobileOpen ? "var(--z-modal)" : undefined }}
      >
        {/* Logo */}
        <div
          aria-hidden="true"
          className={cn(
            "border-b border-[var(--border)] flex items-center h-14",
            collapsed ? "px-0 justify-center" : "px-4",
          )}
        >
          {collapsed ? (
            <Leaf className="w-5 h-5 text-[var(--green)]" />
          ) : (
            <div className="flex items-center gap-2.5 min-w-0">
              <div className="w-7 h-7 rounded-lg bg-[var(--green)] flex items-center justify-center flex-shrink-0">
                <Leaf className="w-4 h-4 text-white" />
              </div>
              <div className="min-w-0">
                <span className="text-[var(--text)] font-bold tracking-tight text-sm block">Treco</span>
                <p className="text-[var(--text-3)] text-xs">agent observability</p>
              </div>
            </div>
          )}
        </div>

        {/* Nav */}
        <nav aria-label="Main navigation" className={cn("flex-1 py-3", collapsed ? "px-2" : "px-3")}>
          <ul className="space-y-0.5">
            {NAV.map((item) => {
              const active = path.startsWith(item.href);
              return (
                <li key={item.href}>
                  <Link
                    href={item.href}
                    onClick={() => setMobileOpen(false)}
                    aria-label={collapsed ? item.label : undefined}
                    aria-current={active ? "page" : undefined}
                    className={cn(
                      "flex items-center rounded-lg text-sm transition-colors duration-150",
                      collapsed ? "justify-center w-9 h-9 mx-auto" : "gap-3 px-3 py-2",
                      "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--green)] focus-visible:ring-offset-1",
                      active
                        ? "bg-[var(--green-3)] text-[var(--green-badge-text)] font-medium"
                        : "text-[var(--text-2)] hover:text-[var(--text)] hover:bg-[var(--surface-2)]",
                    )}
                  >
                    <item.Icon aria-hidden="true" className="w-4 h-4 flex-shrink-0" />
                    {!collapsed && item.label}
                  </Link>
                </li>
              );
            })}
          </ul>
        </nav>

        {/* Bottom nav */}
        <div className={cn("pb-2", collapsed ? "px-2" : "px-3")}>
          <ul className="space-y-0.5">
            {NAV_BOTTOM.map((item) => {
              const active = path.startsWith(item.href);
              return (
                <li key={item.href}>
                  <Link
                    href={item.href}
                    onClick={() => setMobileOpen(false)}
                    aria-label={collapsed ? item.label : undefined}
                    aria-current={active ? "page" : undefined}
                    className={cn(
                      "flex items-center rounded-lg text-sm transition-colors duration-150",
                      collapsed ? "justify-center w-9 h-9 mx-auto" : "gap-3 px-3 py-2",
                      "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--green)] focus-visible:ring-offset-1",
                      active
                        ? "bg-[var(--green-3)] text-[var(--green-badge-text)] font-medium"
                        : "text-[var(--text-2)] hover:text-[var(--text)] hover:bg-[var(--surface-2)]",
                    )}
                  >
                    <item.Icon aria-hidden="true" className="w-4 h-4 flex-shrink-0" />
                    {!collapsed && item.label}
                  </Link>
                </li>
              );
            })}
          </ul>
        </div>

        {/* Footer */}
        <div className={cn(
          "border-t border-[var(--border)] flex items-center",
          collapsed ? "flex-col gap-2 py-3 px-2" : "justify-between px-4 py-3",
        )}>
          {!collapsed && (
            <div aria-hidden="true">
              <p className="text-[var(--text-3)] text-xs">v0.1.0 · open source</p>
            </div>
          )}
          {onToggle && (
            <button
              type="button"
              onClick={onToggle}
              aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"}
              className={cn(
                "flex items-center justify-center rounded-md text-[var(--text-3)] hover:text-[var(--text)] hover:bg-[var(--surface-2)] transition-colors",
                collapsed ? "w-8 h-8" : "w-6 h-6",
              )}
            >
              {collapsed
                ? <ChevronRight aria-hidden="true" className="w-3.5 h-3.5" />
                : <ChevronLeft aria-hidden="true" className="w-3.5 h-3.5" />}
            </button>
          )}
        </div>
      </aside>
    </>
  );
}
