import { cn } from "@/lib/utils";

export function Card({
  children,
  className,
}: {
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <div
      className={cn(
        "bg-surface border border-border-default rounded-xl p-4",
        className
      )}
    >
      {children}
    </div>
  );
}
