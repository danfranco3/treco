"use client";

import { useEffect, useRef, useState, useCallback } from "react";
import { useRouter } from "next/navigation";
import { cn } from "@/lib/utils";
import type { Ticket } from "@/lib/types";

interface Command {
  id: string;
  label: string;
  hint?: string;
  action: () => void;
}

interface CommandPaletteProps {
  tickets?: Ticket[];
}

function highlight(text: string, query: string): React.ReactNode {
  if (!query) return text;
  const idx = text.toLowerCase().indexOf(query.toLowerCase());
  if (idx === -1) return text;
  return (
    <>
      {text.slice(0, idx)}
      <mark className="bg-[var(--green)]/20 text-[var(--green)] rounded-sm not-italic">
        {text.slice(idx, idx + query.length)}
      </mark>
      {text.slice(idx + query.length)}
    </>
  );
}

export function CommandPalette({ tickets = [] }: CommandPaletteProps) {
  const router = useRouter();
  const [open, setOpen]   = useState(false);
  const [query, setQuery] = useState("");
  const [cursor, setCursor] = useState(0);
  const inputRef = useRef<HTMLInputElement>(null);
  const dialogRef = useRef<HTMLDialogElement>(null);

  const close = useCallback(() => {
    setOpen(false);
    setQuery("");
    setCursor(0);
  }, []);

  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === "k") {
        e.preventDefault();
        setOpen((v) => !v);
      }
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, []);

  useEffect(() => {
    if (open) {
      dialogRef.current?.showModal();
      setTimeout(() => inputRef.current?.focus(), 10);
    } else {
      dialogRef.current?.close();
    }
  }, [open]);

  const staticCommands: Command[] = [
    { id: "dashboard", label: "Go to Dashboard",  hint: "nav", action: () => router.push("/dashboard") },
    { id: "tickets",   label: "Go to Tickets",    hint: "nav", action: () => router.push("/tickets") },
    { id: "agents",    label: "Go to Agents",     hint: "nav", action: () => router.push("/agents") },
    { id: "new",       label: "New Ticket",        hint: "action", action: () => router.push("/tickets/new") },
    { id: "import",    label: "Import Tickets",    hint: "action", action: () => router.push("/tickets/import") },
  ];

  const ticketCommands: Command[] = tickets.map((t) => ({
    id: t.id,
    label: t.title,
    hint: t.source_id ?? t.source,
    action: () => router.push(`/tickets/${t.id}`),
  }));

  const all = [...staticCommands, ...ticketCommands];

  const filtered = query
    ? all.filter((c) => c.label.toLowerCase().includes(query.toLowerCase()))
    : all;

  const pick = useCallback((cmd: Command) => {
    cmd.action();
    close();
  }, [close]);

  const onKey = (e: React.KeyboardEvent) => {
    if (e.key === "ArrowDown") {
      e.preventDefault();
      setCursor((c) => Math.min(c + 1, filtered.length - 1));
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setCursor((c) => Math.max(c - 1, 0));
    } else if (e.key === "Enter") {
      if (filtered[cursor]) pick(filtered[cursor]);
    } else if (e.key === "Escape") {
      close();
    }
  };

  return (
    <dialog
      ref={dialogRef}
      onClick={(e) => { if (e.target === dialogRef.current) close(); }}
      onCancel={close}
      className={cn(
        "fixed inset-0 m-auto w-full max-w-lg rounded-xl p-0 overflow-hidden",
        "bg-[var(--surface)] border border-[var(--border)]",
        "shadow-2xl backdrop:bg-[var(--bg)]/70 backdrop:backdrop-blur-sm",
        "animate-slide-in open:flex open:flex-col",
      )}
      suppressHydrationWarning
      style={{ zIndex: "var(--z-modal)" }}
    >
      <div className="flex items-center gap-2 px-4 py-3 border-b border-[var(--border)]">
        <span className="text-[var(--text-3)] text-sm select-none">⌕</span>
        <input
          ref={inputRef}
          value={query}
          onChange={(e) => { setQuery(e.target.value); setCursor(0); }}
          onKeyDown={onKey}
          placeholder="Search tickets, navigate..."
          className="flex-1 bg-transparent text-sm font-mono text-[var(--text)] placeholder:text-[var(--text-3)] outline-none"
        />
        <kbd className="text-[var(--text-3)] text-xs border border-[var(--border)] rounded px-1 py-0.5 font-mono">Esc</kbd>
      </div>

      <ul className="max-h-80 overflow-y-auto py-1">
        {filtered.length === 0 && (
          <li className="px-4 py-3 text-xs text-[var(--text-3)]">No results</li>
        )}
        {filtered.map((cmd, i) => (
          <li
            key={cmd.id}
            onMouseEnter={() => setCursor(i)}
            onClick={() => pick(cmd)}
            className={cn(
              "flex items-center justify-between gap-3 px-4 py-2.5 cursor-pointer text-sm",
              "transition-colors duration-75",
              i === cursor
                ? "bg-[var(--surface-2)] text-[var(--text)]"
                : "text-[var(--text-2)]",
            )}
          >
            <span>{highlight(cmd.label, query)}</span>
            {cmd.hint && (
              <span className="text-xs font-mono text-[var(--text-3)] flex-shrink-0">{cmd.hint}</span>
            )}
          </li>
        ))}
      </ul>

      <div className="px-4 py-2 border-t border-[var(--border)] flex items-center gap-4 text-xs text-[var(--text-3)]">
        <span><kbd className="font-mono">↑↓</kbd> navigate</span>
        <span><kbd className="font-mono">↵</kbd> select</span>
        <span><kbd className="font-mono">⌘K</kbd> toggle</span>
      </div>
    </dialog>
  );
}
