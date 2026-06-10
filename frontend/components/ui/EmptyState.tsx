import { cn } from "@/lib/utils";

interface EmptyStateProps {
  icon?: string;
  title: string;
  sub?: string;
  codeHint?: string;
  actions?: React.ReactNode;
  className?: string;
}

export function EmptyState({ icon, title, sub, codeHint, actions, className }: EmptyStateProps) {
  return (
    <div className={cn("flex flex-col items-center justify-center py-16 text-center gap-2", className)}>
      {icon && <span className="text-2xl text-[var(--text-3)] mb-1">{icon}</span>}
      <p className="text-sm font-medium text-[var(--text-2)]">{title}</p>
      {sub && <p className="text-xs text-[var(--text-3)] max-w-xs">{sub}</p>}
      {codeHint && (
        <code className="code-chip mt-1">{codeHint}</code>
      )}
      {actions && <div className="flex gap-2 mt-3">{actions}</div>}
    </div>
  );
}

export function EmptyAgents() {
  return (
    <EmptyState
      icon="◎"
      title="No agents connected yet"
      sub="Run treco init in your project to connect this workspace."
      codeHint="treco init"
    />
  );
}

export function EmptyTickets({ onImport, onNew }: { onImport?: () => void; onNew?: () => void }) {
  return (
    <EmptyState
      icon="◈"
      title="No tickets yet"
      sub="Import from GitHub, Linear, or Jira — or create one manually."
      actions={
        <>
          {onImport && (
            <button onClick={onImport} className="btn-secondary text-xs">
              Import tickets
            </button>
          )}
          {onNew && (
            <button onClick={onNew} className="btn-primary text-xs">
              New ticket
            </button>
          )}
        </>
      }
    />
  );
}

export function EmptyAgentIdle() {
  return (
    <EmptyState
      icon="◎"
      title="Agent connected, waiting for a ticket"
      sub="Run treco start to assign a ticket to this agent."
      codeHint="treco start"
    />
  );
}
