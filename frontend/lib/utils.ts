import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";
import type { Ticket } from "./types";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export function formatRelativeTime(iso: string): string {
  const diff = Date.now() - new Date(iso).getTime();
  const s = Math.floor(diff / 1000);
  if (s < 60) return `${s}s ago`;
  const m = Math.floor(s / 60);
  if (m < 60) return `${m}m ago`;
  const h = Math.floor(m / 60);
  if (h < 24) return `${h}h ago`;
  return new Date(iso).toLocaleDateString();
}

export function formatTime(iso: string): string {
  return new Date(iso).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" });
}

export function criteriaProgress(criteria: { done: boolean }[]): number {
  if (!criteria.length) return 0;
  return Math.round((criteria.filter((c) => c.done).length / criteria.length) * 100);
}

export function toMap<T extends { id: string }>(items: T[]): Record<string, T> {
  return Object.fromEntries(items.map((i) => [i.id, i]));
}

export function toNameMap(items: { id: string; name: string }[]): Record<string, string> {
  return Object.fromEntries(items.map((i) => [i.id, i.name]));
}

export function sortChronological<T extends { created_at: string }>(items: T[]): T[] {
  return [...items].sort((a, b) => new Date(a.created_at).getTime() - new Date(b.created_at).getTime());
}

// Haiku 4.5 pricing: $0.80/1M input, $4.00/1M output
export function formatCost(tokensIn: number, tokensOut: number): string {
  const cost = (tokensIn * 0.0000008) + (tokensOut * 0.000004);
  return `$${cost.toFixed(4)}`;
}

export function buildDefaultPrompt(ticket: Ticket): string {
  const criteria = ticket.acceptance_criteria
    .map((c) => `- [${c.done ? "x" : " "}] ${c.text}`)
    .join("\n");
  return (
    `Implement ticket: ${ticket.title}\n\n` +
    (ticket.description ? `${ticket.description}\n\n` : "") +
    `Acceptance criteria:\n${criteria || "(none extracted — use your judgement)"}\n\n` +
    "Run `treco check <criterion-id>` as you complete each criterion, then `treco done` when finished."
  );
}
