import type { Agent, AgentEvent, Ticket } from "@/lib/types";

interface StatBarProps {
  agents: Agent[];
  tickets: Ticket[];
  events: AgentEvent[];
}

export function StatBar({ agents, tickets, events }: StatBarProps) {
  const activeAgents = agents.filter((a) => a.status === "working").length;
  const openTickets  = tickets.filter((t) => t.status === "open" || t.status === "in_progress").length;
  const doneTickets  = tickets.filter((t) => t.status === "done").length;

  const todayStart = new Date();
  todayStart.setHours(0, 0, 0, 0);
  const criteriaToday = events.filter(
    (e) => e.event_type === "criterion_checked" && new Date(e.created_at) >= todayStart
  ).length;

  const stats = [
    { icon: "◎", value: activeAgents, label: "active" },
    { icon: "◈", value: openTickets,  label: "open" },
    { icon: "✓", value: doneTickets,  label: "done" },
    { icon: "⬡", value: criteriaToday, label: "criteria today" },
  ];

  return (
    <div className="flex flex-wrap gap-x-6 gap-y-2 items-center px-4 py-2 bg-[var(--surface)] rounded-lg border border-[var(--border)]">
      {stats.map((s, i) => (
        <span key={s.label} className="flex items-center gap-2">
          {i > 0 && <span className="text-[var(--border)] select-none hidden sm:inline">·</span>}
          <span className="font-mono text-sm text-[var(--cyan)]">{s.icon} {s.value}</span>
          <span className="text-xs text-[var(--text-2)]">{s.label}</span>
        </span>
      ))}
    </div>
  );
}
