"use client";

import { useEffect, useRef } from "react";
import { X } from "lucide-react";
import { cn } from "@/lib/utils";

interface ShortcutsModalProps {
  open: boolean;
  onClose: () => void;
}

const SECTIONS = [
  {
    title: "Navigation",
    shortcuts: [
      { keys: ["g", "d"], label: "Go to Dashboard" },
      { keys: ["g", "t"], label: "Go to Tickets" },
      { keys: ["g", "a"], label: "Go to Agents" },
    ],
  },
  {
    title: "Actions",
    shortcuts: [
      { keys: ["n"], label: "New Ticket" },
      { keys: ["⌘", "k"], label: "Command Palette" },
    ],
  },
  {
    title: "Help",
    shortcuts: [
      { keys: ["?"], label: "Show Keyboard Shortcuts" },
    ],
  },
];

export function ShortcutsModal({ open, onClose }: ShortcutsModalProps) {
  const dialogRef = useRef<HTMLDialogElement>(null);

  useEffect(() => {
    if (open) {
      dialogRef.current?.showModal();
    } else {
      dialogRef.current?.close();
    }
  }, [open]);

  return (
    <dialog
      ref={dialogRef}
      onClick={(e) => { if (e.target === dialogRef.current) onClose(); }}
      onCancel={onClose}
      aria-label="Keyboard shortcuts"
      className={cn(
        "fixed inset-0 m-auto w-full max-w-md rounded-xl p-0 overflow-hidden",
        "bg-[var(--surface)] border border-[var(--border)]",
        "shadow-2xl backdrop:bg-[var(--bg)]/70 backdrop:backdrop-blur-sm",
        "open:flex open:flex-col",
      )}
      suppressHydrationWarning
      style={{ zIndex: "var(--z-modal)" }}
    >
      <div className="flex items-center justify-between px-5 py-4 border-b border-[var(--border)]">
        <h2 className="text-sm font-semibold text-[var(--text)]">Keyboard Shortcuts</h2>
        <button
          type="button"
          onClick={onClose}
          aria-label="Close shortcuts"
          className="text-[var(--text-3)] hover:text-[var(--text)] transition-colors"
        >
          <X className="w-4 h-4" aria-hidden="true" />
        </button>
      </div>

      <div className="px-5 py-4 space-y-5 overflow-y-auto">
        {SECTIONS.map((section) => (
          <div key={section.title}>
            <p className="text-xs font-medium text-[var(--text-3)] uppercase tracking-wider mb-2">
              {section.title}
            </p>
            <ul className="space-y-1.5">
              {section.shortcuts.map((s) => (
                <li key={s.label} className="flex items-center justify-between">
                  <span className="text-sm text-[var(--text-2)]">{s.label}</span>
                  <span className="flex items-center gap-1">
                    {s.keys.map((k, i) => (
                      <kbd
                        key={i}
                        className="text-xs font-mono text-[var(--text-2)] bg-[var(--surface-2)] border border-[var(--border)] rounded px-1.5 py-0.5"
                      >
                        {k}
                      </kbd>
                    ))}
                  </span>
                </li>
              ))}
            </ul>
          </div>
        ))}
      </div>

      <div className="px-5 py-3 border-t border-[var(--border)] text-xs text-[var(--text-3)]">
        Shortcuts inactive when typing in a field.
      </div>
    </dialog>
  );
}
