"use client";

import { useEffect, useRef } from "react";
import { Play, Trash2 } from "lucide-react";

interface TicketContextMenuProps {
  x: number;
  y: number;
  onImplement: () => void;
  onDelete: () => void;
  onClose: () => void;
}

export function TicketContextMenu({ x, y, onImplement, onDelete, onClose }: TicketContextMenuProps) {
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    function handlePointer(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) onClose();
    }
    function handleKey(e: KeyboardEvent) {
      if (e.key === "Escape") onClose();
    }
    document.addEventListener("mousedown", handlePointer);
    document.addEventListener("keydown", handleKey);
    return () => {
      document.removeEventListener("mousedown", handlePointer);
      document.removeEventListener("keydown", handleKey);
    };
  }, [onClose]);

  return (
    <div
      ref={ref}
      style={{ position: "fixed", top: y, left: x }}
      className="z-50 w-44 bg-[var(--surface)] border border-[var(--border)] rounded-lg shadow-lg overflow-hidden py-1"
    >
      <button
        onClick={() => {
          onClose();
          onImplement();
        }}
        className="w-full flex items-center gap-2 text-left px-3 py-2 text-sm text-[var(--text)] hover:bg-[var(--surface-2)] transition-colors"
      >
        <Play className="w-4 h-4" />
        Implement
      </button>
      <button
        onClick={() => {
          onClose();
          onDelete();
        }}
        className="w-full flex items-center gap-2 text-left px-3 py-2 text-sm text-red-500 hover:bg-[var(--surface-2)] transition-colors"
      >
        <Trash2 className="w-4 h-4" />
        Delete
      </button>
    </div>
  );
}
