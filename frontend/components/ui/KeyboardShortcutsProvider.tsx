"use client";

import { useKeyboardShortcuts } from "@/hooks/useKeyboardShortcuts";
import { ShortcutsModal } from "./ShortcutsModal";

export function KeyboardShortcutsProvider() {
  const { isModalOpen, setIsModalOpen } = useKeyboardShortcuts();

  return (
    <ShortcutsModal 
      open={isModalOpen} 
      onClose={() => setIsModalOpen(false)} 
    />
  );
}
