import type { ReactNode } from "react";

type ColumnColor = "neutral" | "blue" | "amber" | "green";

const BORDER: Record<ColumnColor, string> = {
  neutral: "border-[var(--surface-3)]",
  blue:    "border-blue-400",
  amber:   "border-[var(--amber)]",
  green:   "border-[var(--green)]",
};

interface BoardColumnProps {
  title: string;
  color: ColumnColor;
  count: number;
  children: ReactNode;
}

export function BoardColumn({ title, color, count, children }: BoardColumnProps) {
  return (
    <div className="flex flex-col gap-2 min-w-0">
      {/* Header */}
      <div className={`flex items-center justify-between pb-2 border-b-2 ${BORDER[color]}`}>
        <span className="text-[11px] font-bold tracking-widest uppercase text-[var(--text-3)]">
          {title}
        </span>
        <span className="text-[11px] font-semibold tabular-nums text-[var(--text-3)] bg-[var(--surface-2)] rounded-full px-2 py-0.5">
          {count}
        </span>
      </div>

      {/* Cards */}
      <div className="flex flex-col gap-2 overflow-y-auto">
        {count === 0 ? (
          <div className="border-2 border-dashed border-[var(--border)] rounded-lg px-3 py-5 text-center text-[12px] text-[var(--text-3)]">
            Empty
          </div>
        ) : (
          children
        )}
      </div>
    </div>
  );
}
