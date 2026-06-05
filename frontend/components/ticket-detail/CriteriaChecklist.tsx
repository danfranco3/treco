import type { AgentEvent, Criterion } from "@/lib/types";

interface CriteriaChecklistProps {
  criteria: Criterion[];
  events: AgentEvent[];
  agentNames: Record<string, string>;
}

import { CriterionItem } from "./CriterionItem";
import { EmptyState } from "@/components/ui/EmptyState";

export function CriteriaChecklist({ criteria, events, agentNames }: CriteriaChecklistProps) {
  if (!criteria.length) {
    return <EmptyState icon="◈" title="No acceptance criteria" sub="Add criteria to the ticket or use LLM extraction" />;
  }

  const checkedMap: Record<string, { agentId: string; at: string }> = {};
  const failedMap: Record<string, string> = {};

  for (const ev of events) {
    if (!ev.criterion_id) continue;
    if (ev.event_type === "criterion_checked") {
      checkedMap[ev.criterion_id] = { agentId: ev.agent_id, at: ev.created_at };
    }
    if (ev.event_type === "criterion_failed") {
      failedMap[ev.criterion_id] = ev.created_at;
    }
  }

  return (
    <div className="space-y-2">
      {criteria.map((c) => (
        <CriterionItem
          key={c.id}
          criterion={c}
          agentName={checkedMap[c.id] ? agentNames[checkedMap[c.id].agentId] : undefined}
          checkedAt={checkedMap[c.id]?.at}
          failedAt={failedMap[c.id]}
        />
      ))}
    </div>
  );
}
