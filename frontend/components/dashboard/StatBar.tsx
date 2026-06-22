import { Bot, Ticket, CheckCircle2, Sparkles } from "lucide-react";
import type { Agent, AgentEvent, Ticket as TicketType } from "@/lib/types";

interface StatBarProps {
  agents: Agent[];
  tickets: TicketType[];
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
    { Icon: Bot,          value: activeAgents,  label: "active agents" },
    { Icon: Ticket,       value: openTickets,   label: "open tickets" },
    { Icon: CheckCircle2, value: doneTickets,   label: "done" },
    { Icon: Sparkles,     value: criteriaToday, label: "criteria today" },
  ];

  return (
    <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
      {stats.map((s) => (
        <div key={s.label} className="flex items-center gap-3 bg-[var(--surface)] border border-[var(--border)] rounded-xl px-4 py-3 shadow-card">
          <div aria-hidden="true" className="w-8 h-8 rounded-lg bg-[var(--green-3)] flex items-center justify-center flex-shrink-0">
            <s.Icon className="w-4 h-4 text-[var(--green)]" />
          </div>
          <div>
            <p className="text-xl font-bold text-[var(--text)] leading-none">{s.value}</p>
            <p className="text-xs text-[var(--text-3)] mt-0.5">{s.label}</p>
          </div>
        </div>
      ))}
    </div>
  );
}
