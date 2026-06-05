export function EmptyState({ icon, title, sub }: { icon: string; title: string; sub?: string }) {
  return (
    <div className="flex flex-col items-center justify-center py-16 text-center">
      <span className="text-4xl mb-3 opacity-40">{icon}</span>
      <p className="text-text-muted text-sm font-medium">{title}</p>
      {sub && <p className="text-text-muted text-xs mt-1 opacity-70">{sub}</p>}
    </div>
  );
}
