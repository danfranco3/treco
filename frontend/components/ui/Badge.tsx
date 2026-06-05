import { cn } from "@/lib/utils";

const STATUS_STYLES: Record<string, string> = {
  idle:        "bg-gray-800 text-text-muted border-gray-700",
  working:     "bg-cyan-brand/10 text-cyan-brand border-cyan-brand/30",
  done:        "bg-green-brand/10 text-green-brand border-green-brand/30",
  error:       "bg-red-brand/10 text-red-brand border-red-brand/30",
  open:        "bg-amber-brand/10 text-amber-brand border-amber-brand/30",
  in_progress: "bg-cyan-brand/10 text-cyan-brand border-cyan-brand/30",
  jira:        "bg-blue-900/40 text-blue-300 border-blue-800",
  linear:      "bg-violet-900/40 text-violet-300 border-violet-800",
  github:      "bg-gray-800 text-gray-300 border-gray-700",
  asana:       "bg-pink-900/40 text-pink-300 border-pink-800",
  custom:      "bg-surface-2 text-text-muted border-border-default",
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
        STATUS_STYLES[key] ?? "bg-surface-2 text-text-muted border-border-default",
        className
      )}
    >
      {label}
    </span>
  );
}
