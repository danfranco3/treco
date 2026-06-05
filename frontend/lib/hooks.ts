"use client";

import useSWR from "swr";
import {
  fetchAgents,
  fetchTicket,
  fetchTicketCost,
  fetchTicketEvents,
  fetchTickets,
} from "./api";

export function useTickets(workspaceId: string) {
  return useSWR(
    workspaceId ? ["tickets", workspaceId] : null,
    () => fetchTickets(workspaceId),
    { refreshInterval: 10_000 }
  );
}

export function useTicket(ticketId: string) {
  return useSWR(
    ticketId ? ["ticket", ticketId] : null,
    () => fetchTicket(ticketId),
    { refreshInterval: 5_000 }
  );
}

export function useAgents(workspaceId: string) {
  return useSWR(
    workspaceId ? ["agents", workspaceId] : null,
    () => fetchAgents(workspaceId),
    { refreshInterval: 3_000 }
  );
}

export function useTicketEvents(ticketId: string) {
  return useSWR(
    ticketId ? ["events", ticketId] : null,
    () => fetchTicketEvents(ticketId),
    { refreshInterval: 3_000 }
  );
}

export function useTicketCost(ticketId: string) {
  return useSWR(
    ticketId ? ["cost", ticketId] : null,
    () => fetchTicketCost(ticketId),
    { refreshInterval: 5_000 }
  );
}
