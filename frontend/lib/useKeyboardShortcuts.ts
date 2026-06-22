"use client";

import { useEffect, useRef } from "react";
import { useRouter } from "next/navigation";

function isTypingTarget(el: EventTarget | null): boolean {
  if (!(el instanceof HTMLElement)) return false;
  const tag = el.tagName.toLowerCase();
  return (
    tag === "input" ||
    tag === "textarea" ||
    tag === "select" ||
    el.isContentEditable
  );
}

interface Options {
  onShowShortcuts: () => void;
  onNewTicket: () => void;
}

export function useKeyboardShortcuts({ onShowShortcuts, onNewTicket }: Options) {
  const router = useRouter();
  // pending chord key — set to "g" when user presses g, cleared after timeout or on next key
  const chordRef = useRef<string | null>(null);
  const chordTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    const clearChord = () => {
      chordRef.current = null;
      if (chordTimer.current) {
        clearTimeout(chordTimer.current);
        chordTimer.current = null;
      }
    };

    const handler = (e: KeyboardEvent) => {
      if (e.metaKey || e.ctrlKey || e.altKey) return;
      if (isTypingTarget(e.target)) return;

      if (chordRef.current === "g") {
        clearChord();
        if (e.key === "d") { e.preventDefault(); router.push("/dashboard"); }
        else if (e.key === "t") { e.preventDefault(); router.push("/tickets"); }
        else if (e.key === "a") { e.preventDefault(); router.push("/agents"); }
        return;
      }

      if (e.key === "g") {
        e.preventDefault();
        chordRef.current = "g";
        chordTimer.current = setTimeout(clearChord, 1000);
        return;
      }

      if (e.key === "n") {
        e.preventDefault();
        onNewTicket();
        return;
      }

      if (e.key === "?") {
        e.preventDefault();
        onShowShortcuts();
        return;
      }
    };

    window.addEventListener("keydown", handler);
    return () => {
      window.removeEventListener("keydown", handler);
      clearChord();
    };
  }, [router, onShowShortcuts, onNewTicket]);
}
