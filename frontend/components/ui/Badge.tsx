import { cn } from "@/lib/utils";

const STATUS_STYLES: Record<string, string> = {
  idle:        "bg-[var(--surface-2)] text-[var(--text-3)] border-[var(--border)]",
  working:     "bg-[var(--green-3)] text-[var(--green-badge-text)] border-[var(--green)]/25",
  done:        "bg-[var(--green-3)] text-[var(--green-badge-text)] border-[var(--green)]/25",
  error:       "bg-red-50 text-red-600 border-red-200",
  open:        "bg-amber-50 text-amber-600 border-amber-200",
  in_progress: "bg-blue-50 text-blue-600 border-blue-200",
  jira:        "bg-blue-50 text-blue-600 border-blue-200",
  linear:      "bg-violet-50 text-violet-600 border-violet-200",
  github:      "bg-[var(--surface-2)] text-[var(--text-2)] border-[var(--border)]",
  asana:       "bg-pink-50 text-pink-600 border-pink-200",
  custom:      "bg-[var(--surface-2)] text-[var(--text-3)] border-[var(--border)]",
};

interface BadgeProps {
  label: string;
  variant?: string;
  className?: string;
}

export function Badge({ label, variant, className }: BadgeProps) {
  const key = variant ?? label.toLowerCase().replace(/\s/g, "_");
  return (
    <span
      className={cn(
        "inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium border",
        STATUS_STYLES[key] ?? "bg-[var(--surface-2)] text-[var(--text-3)] border-[var(--border)]",
        className
      )}
    >
      {label}
    </span>
  );
}
