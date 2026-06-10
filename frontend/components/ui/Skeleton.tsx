import { cn } from "@/lib/utils";

export function Skeleton({ className }: { className?: string }) {
  return (
    <div
      className={cn("rounded skeleton-shimmer", className)}
      aria-hidden="true"
    />
  );
}

export function SkeletonTicketRows({ count = 5 }: { count?: number }) {
  return (
    <div className="divide-y divide-[var(--border)]">
      {Array.from({ length: count }).map((_, i) => (
        <div key={i} className="flex items-center gap-4 px-4 py-3">
          <div className="flex-1 flex flex-col gap-1.5">
            <Skeleton className="h-3 w-16" />
            <Skeleton className="h-4 w-2/3" />
          </div>
          <Skeleton className="h-4 w-16" />
          <Skeleton className="h-4 w-20" />
        </div>
      ))}
    </div>
  );
}

export function SkeletonAgentCards({ count = 2 }: { count?: number }) {
  return (
    <>
      {Array.from({ length: count }).map((_, i) => (
        <div key={i} className="bg-[var(--surface)] border border-[var(--border)] rounded-xl p-4 flex flex-col gap-3">
          <div className="flex items-center gap-2">
            <Skeleton className="h-3 w-3 rounded-full" />
            <Skeleton className="h-4 w-32" />
          </div>
          <Skeleton className="h-16 w-full rounded-lg" />
        </div>
      ))}
    </>
  );
}

export function SkeletonStatStrip() {
  return (
    <div className="flex gap-6 items-center px-4 py-2 bg-[var(--surface)] rounded-lg border border-[var(--border)]">
      {Array.from({ length: 3 }).map((_, i) => (
        <span key={i} className="flex items-center gap-2">
          <Skeleton className="h-4 w-6" />
          <Skeleton className="h-3 w-20" />
        </span>
      ))}
    </div>
  );
}
