import type { CSSProperties } from "react";
import { cn } from "@/lib/utils";

export function Card({
  children,
  className,
  style,
}: {
  children: React.ReactNode;
  className?: string;
  style?: CSSProperties;
}) {
  return (
    <div
      className={cn(
        "bg-[var(--surface)] border border-[var(--border)] rounded-xl p-4 shadow-card",
        className
      )}
      style={style}
    >
      {children}
    </div>
  );
}
