import type { Criterion } from "@/lib/types";
import { cn, formatRelativeTime } from "@/lib/utils";

interface CriterionItemProps {
  criterion: Criterion;
  agentName?: string;
  checkedAt?: string;
  failedAt?: string;
}

export function CriterionItem({ criterion, agentName, checkedAt, failedAt }: CriterionItemProps) {
  const done = criterion.done;
  const failed = !!failedAt && !done;

  return (
    <div className={cn(
      "flex items-start gap-3 px-4 py-3 rounded-lg border transition-all duration-300",
      done  && "bg-green-brand/5 border-green-brand/20",
      failed && "bg-red-brand/5 border-red-brand/20",
      !done && !failed && "bg-surface-2 border-border-default"
    )}>
      <div className="mt-0.5 flex-shrink-0" aria-hidden="true">
        {done ? (
          <span className="flex h-5 w-5 items-center justify-center rounded-full bg-green-brand/20 text-green-brand text-xs">✓</span>
        ) : failed ? (
          <span className="flex h-5 w-5 items-center justify-center rounded-full bg-red-brand/20 text-red-brand text-xs">✗</span>
        ) : (
          <span className="flex h-5 w-5 items-center justify-center rounded-full border border-border-default text-text-muted text-xs">○</span>
        )}
      </div>
      <span className="sr-only">{done ? "Completed" : failed ? "Failed" : "Pending"}:</span>

      <div className="flex-1 min-w-0">
        <p className={cn("text-sm", done ? "text-text-muted line-through" : "text-text-primary")}>
          {criterion.text}
        </p>

        {(agentName || checkedAt) && (
          <div className="flex items-center gap-2 mt-1.5">
            {agentName && (
              <span className="text-xs px-1.5 py-0 rounded bg-surface border border-border-default text-text-muted">
                {agentName}
              </span>
            )}
            {checkedAt && (
              <span className="text-xs text-text-muted">{formatRelativeTime(checkedAt)}</span>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
