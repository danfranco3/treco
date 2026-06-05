import { cn } from "@/lib/utils";

interface PulseRingProps {
  active?: boolean;
  error?: boolean;
  size?: "sm" | "md";
}

export function PulseRing({ active, error, size = "md" }: PulseRingProps) {
  const dim = size === "sm" ? "h-2.5 w-2.5" : "h-3 w-3";
  const color = error ? "bg-red-brand" : "bg-cyan-brand";

  if (!active && !error) {
    return <span className={cn("inline-flex rounded-full bg-gray-600", dim)} />;
  }

  return (
    <span className={cn("relative inline-flex", dim)}>
      {active && !error && (
        <span
          className={cn(
            "ping-slow absolute inline-flex h-full w-full rounded-full opacity-75",
            color
          )}
        />
      )}
      <span className={cn("relative inline-flex rounded-full", dim, color)} />
    </span>
  );
}
