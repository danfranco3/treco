"use client";

import { useEffect, useState, useRef } from "react";
import { useRouter } from "next/navigation";

export function useKeyboardShortcuts() {
  const router = useRouter();
  const [isModalOpen, setIsModalOpen] = useState(false);
  const sequenceTimer = useRef<NodeJS.Timeout | null>(null);
  const sequenceKey = useRef<string | null>(null);

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      // Ignore if focus is in an input or textarea
      const target = e.target as HTMLElement;
      if (
        target instanceof HTMLInputElement ||
        target instanceof HTMLTextAreaElement ||
        target.isContentEditable ||
        target.tagName === 'SELECT'
      ) {
        return;
      }
      
      // Ignore if modifier keys are pressed (avoid browser defaults)
      if (e.ctrlKey || e.altKey || e.metaKey) {
        return;
      }

      const key = e.key;

      if (sequenceKey.current === "g") {
        let matched = true;
        if (key === "d") {
          router.push("/dashboard");
        } else if (key === "t") {
          router.push("/tickets");
        } else if (key === "a") {
          router.push("/agents");
        } else {
          matched = false;
        }

        if (matched) {
          e.preventDefault();
          sequenceKey.current = null;
          if (sequenceTimer.current) clearTimeout(sequenceTimer.current);
          return;
        }
        
        sequenceKey.current = null;
        if (sequenceTimer.current) clearTimeout(sequenceTimer.current);
      }

      if (key === "n") {
        e.preventDefault();
        router.push("/tickets/new");
      } else if (key === "?") {
        e.preventDefault();
        setIsModalOpen(true);
      } else if (key === "g") {
        e.preventDefault();
        sequenceKey.current = "g";
        if (sequenceTimer.current) clearTimeout(sequenceTimer.current);
        sequenceTimer.current = setTimeout(() => {
          sequenceKey.current = null;
        }, 1000);
      }
    };

    window.addEventListener("keydown", handleKeyDown);
    return () => {
      window.removeEventListener("keydown", handleKeyDown);
      if (sequenceTimer.current) clearTimeout(sequenceTimer.current);
    };
  }, [router]);

  return {
    isModalOpen,
    setIsModalOpen,
  };
}
