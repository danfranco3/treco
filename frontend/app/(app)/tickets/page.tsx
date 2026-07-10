"use client";

import { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import useSWR from "swr";
import { fetchTickets, deleteTicket, implementTicket } from "@/lib/api";
import { useWorkspace } from "@/lib/workspace";
import { TicketRow } from "@/components/tickets/TicketRow";
import { TicketContextMenu } from "@/components/tickets/TicketContextMenu";
import { EmptyTickets } from "@/components/ui/EmptyState";
import { Spinner } from "@/components/ui/Spinner";
import { Card } from "@/components/ui/Card";
import { loadImplSettings } from "@/lib/impl-settings";
import type { Ticket } from "@/lib/types";

const PAGE_SIZE = 50;

export default function TicketsPage() {
  const router = useRouter();
  const { workspaceId } = useWorkspace();
  const [offset, setOffset] = useState(0);
  const [menu, setMenu] = useState<{ x: number; y: number; ticket: Ticket } | null>(null);

  const { data: tickets = [], isLoading, mutate } = useSWR(
    workspaceId ? ["tickets", workspaceId, offset] : null,
    () => fetchTickets(workspaceId, PAGE_SIZE, offset),
    { refreshInterval: 30_000, revalidateOnFocus: false }
  );

  function handleContextMenu(e: React.MouseEvent, ticket: Ticket) {
    e.preventDefault();
    setMenu({ x: e.clientX, y: e.clientY, ticket });
  }

  async function handleDelete(ticket: Ticket) {
    await deleteTicket(ticket.id);
    mutate();
  }

  async function handleImplement(ticket: Ticket) {
    const s = loadImplSettings();
    await implementTicket(ticket.id, { method: "claude_code", model: s.model, system_prompt: s.system_prompt, skip_permissions: s.skip_permissions });
    mutate();
  }

  return (
    <div className="flex flex-col gap-6">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-bold text-text-primary">Tickets</h1>
        <div className="flex items-center gap-3">
          <span className="text-xs text-text-muted">{tickets.length} tickets</span>
          {isLoading && <Spinner />}
          <Link
            href="/tickets/new"
            className="px-3 py-1.5 rounded-lg text-sm bg-green-brand text-white font-semibold hover:bg-green-brand/90 transition-colors"
          >
            New Ticket
          </Link>
        </div>
      </div>

      <Card className="p-0 overflow-hidden">
        {!isLoading && tickets.length === 0 ? (
          <EmptyTickets
            onImport={() => {}}
            onNew={() => router.push("/tickets/new")}
          />
        ) : (
          <div className="divide-y divide-border-default">
            {tickets.map((ticket) => (
              <TicketRow key={ticket.id} ticket={ticket} onContextMenu={handleContextMenu} />
            ))}
          </div>
        )}
      </Card>

      {menu && (
        <TicketContextMenu
          x={menu.x}
          y={menu.y}
          onImplement={() => handleImplement(menu.ticket)}
          onDelete={() => handleDelete(menu.ticket)}
          onClose={() => setMenu(null)}
        />
      )}

      <div className="flex justify-between items-center">
        <button
          onClick={() => setOffset(Math.max(0, offset - PAGE_SIZE))}
          disabled={offset === 0}
          className="text-xs text-text-muted hover:text-text-primary disabled:opacity-30 disabled:cursor-not-allowed"
        >
          ← Previous
        </button>
        <span className="text-xs text-text-muted">
          {tickets.length === 0 ? "0" : `${offset + 1}–${offset + tickets.length}`}
        </span>
        <button
          onClick={() => setOffset(offset + PAGE_SIZE)}
          disabled={tickets.length < PAGE_SIZE}
          className="text-xs text-text-muted hover:text-text-primary disabled:opacity-30 disabled:cursor-not-allowed"
        >
          Next →
        </button>
      </div>
    </div>
  );
}
