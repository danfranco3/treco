// Per-million-token pricing. Update as models change.
const PRICING: Record<string, { input: number; output: number }> = {
  "claude-opus-4-8":              { input: 15.0,  output: 75.0  },
  "claude-sonnet-4-6":            { input: 3.0,   output: 15.0  },
  "claude-haiku-4-5-20251001":    { input: 0.8,   output: 4.0   },
  "gpt-4o":                       { input: 2.5,   output: 10.0  },
  "gpt-4o-mini":                  { input: 0.15,  output: 0.6   },
  // fallback applied when model is null or unknown
  _default:                       { input: 3.0,   output: 15.0  },
};

export function estimateCost(
  tokensIn: number,
  tokensOut: number,
  model: string | null
): number {
  const rates = PRICING[model ?? "_default"] ?? PRICING["_default"];
  return (tokensIn / 1_000_000) * rates.input + (tokensOut / 1_000_000) * rates.output;
}

export function formatCost(usd: number): string {
  if (usd < 0.001) return "$0.00";
  if (usd < 0.01) return `$${usd.toFixed(4)}`;
  return `$${usd.toFixed(3)}`;
}

export function formatTokens(n: number): string {
  return new Intl.NumberFormat().format(n);
}
