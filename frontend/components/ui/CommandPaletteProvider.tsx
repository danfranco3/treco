"use client";

import { useWorkspace } from "@/lib/workspace";
import { useTickets } from "@/lib/hooks";
import { CommandPalette } from "./CommandPalette";

export function CommandPaletteProvider() {
  const { workspaceId } = useWorkspace();
  const { data: tickets = [] } = useTickets(workspaceId);
  return <CommandPalette tickets={tickets} />;
}
