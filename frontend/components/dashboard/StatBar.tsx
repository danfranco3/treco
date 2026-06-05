import type { Agent, AgentEvent, Ticket } from "@/lib/types";
import { Card } from "@/components/ui/Card";

interface StatBarProps {
  agents: Agent[];
  tickets: Ticket[];
  events: AgentEvent[];
}

export function StatBar({ agents, tickets, events }: StatBarProps) {
  const activeAgents = agents.filter((a) => a.status === "working").length;
  const openTickets = tickets.filter((t) => t.status === "open" || t.status === "in_progress").length;

  const todayStart = new Date();
  todayStart.setHours(0, 0, 0, 0);
  const criteriaToday = events.filter(
    (e) => e.event_type === "criterion_checked" && new Date(e.created_at) >= todayStart
  ).length;

  const stats = [
    { label: "Active Agents",       value: activeAgents,  color: "text-cyan-brand",   icon: "◎" },
    { label: "Open Tickets",         value: openTickets,   color: "text-amber-brand",  icon: "◈" },
    { label: "Criteria Done Today",  value: criteriaToday, color: "text-green-brand",  icon: "✓" },
  ];

  return (
    <div className="grid grid-cols-3 gap-4">
      {stats.map((s) => (
        <Card key={s.label} className="flex items-center gap-4">
          <span className={`text-3xl ${s.color}`}>{s.icon}</span>
          <div>
            <p className={`text-3xl font-bold font-mono ${s.color}`}>{s.value}</p>
            <p className="text-text-muted text-xs mt-0.5">{s.label}</p>
          </div>
        </Card>
      ))}
    </div>
  );
}
