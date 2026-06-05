import { estimateCost, formatCost } from "@/lib/cost";

interface CostPillProps {
  tokensIn: number;
  tokensOut: number;
  model?: string | null;
}

export function CostPill({ tokensIn, tokensOut, model }: CostPillProps) {
  const usd = estimateCost(tokensIn, tokensOut, model ?? null);
  return (
    <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs bg-purple-brand/10 border border-purple-brand/30 text-purple-brand font-mono">
      {formatCost(usd)}
    </span>
  );
}
