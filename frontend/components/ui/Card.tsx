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
        "bg-surface border border-border-default rounded-xl p-4",
        className
      )}
      style={style}
    >
      {children}
    </div>
  );
}
