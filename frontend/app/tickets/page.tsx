"use client";

import { useState } from "react";
import Link from "next/link";
import useSWR from "swr";
import { useWorkspace } from "@/lib/workspace";
import { fetchTickets } from "@/lib/api";
import { TicketRow } from "@/components/tickets/TicketRow";
import { TicketFilter } from "@/components/tickets/TicketFilter";
import { EmptyState } from "@/components/ui/EmptyState";
import { Spinner } from "@/components/ui/Spinner";
import { Card } from "@/components/ui/Card";

const PAGE_SIZE = 50;

export default function TicketsPage() {
  const { workspaceId } = useWorkspace();
  const [source, setSource] = useState("all");
  const [status, setStatus] = useState("all");
  const [offset, setOffset] = useState(0);

  const { data: tickets = [], isLoading } = useSWR(
    workspaceId ? ["tickets", workspaceId, offset] : null,
    () => fetchTickets(workspaceId, PAGE_SIZE, offset),
    { refreshInterval: 30_000, revalidateOnFocus: false }
  );

  const filtered = tickets.filter((t) => {
    if (source !== "all" && t.source !== source) return false;
    if (status !== "all" && t.status !== status) return false;
    return true;
  });

  return (
    <div className="flex flex-col gap-6">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-bold text-text-primary">Tickets</h1>
        <div className="flex items-center gap-3">
          <span className="text-xs text-text-muted">{filtered.length} shown</span>
          {isLoading && <Spinner />}
          <Link
            href="/tickets/import"
            className="px-3 py-1.5 rounded-lg text-sm border border-border-default text-text-muted hover:text-text-primary hover:border-gray-500 transition-colors"
          >
            Import
          </Link>
          <Link
            href="/tickets/new"
            className="px-3 py-1.5 rounded-lg text-sm bg-cyan-brand text-bg font-semibold hover:bg-cyan-brand/90 transition-colors"
          >
            New Ticket
          </Link>
        </div>
      </div>

      <TicketFilter source={source} status={status} onSource={setSource} onStatus={setStatus} />

      <Card className="p-0 overflow-hidden">
        {!filtered.length ? (
          <EmptyState icon="◈" title="No tickets found" sub="Import tickets or create one via the API" />
        ) : (
          <div className="divide-y divide-border-default">
            {filtered.map((ticket) => (
              <TicketRow key={ticket.id} ticket={ticket} />
            ))}
          </div>
        )}
      </Card>

      <div className="flex justify-between items-center">
        <button
          onClick={() => setOffset(Math.max(0, offset - PAGE_SIZE))}
          disabled={offset === 0}
          className="text-xs text-text-muted hover:text-text-primary disabled:opacity-30 disabled:cursor-not-allowed"
        >
          ← Previous
        </button>
        <span className="text-xs text-text-muted">
          {offset + 1}–{offset + tickets.length}
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
