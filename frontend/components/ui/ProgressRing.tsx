"use client";

const R = 52;
const CIRC = 2 * Math.PI * R;

interface ProgressRingProps {
  pct: number;
  size?: number;
  strokeWidth?: number;
  label?: string;
}

export function ProgressRing({ pct, size = 128, strokeWidth = 8, label }: ProgressRingProps) {
  const offset = CIRC * (1 - pct / 100);
  const color = pct === 100 ? "#10b981" : pct > 50 ? "#06b6d4" : "#f59e0b";

  return (
    <div
      role="img"
      aria-label={`${pct}% complete${label ? `: ${label}` : ""}`}
      className="relative inline-flex items-center justify-center"
      style={{ width: size, height: size }}
    >
      <svg aria-hidden="true" width={size} height={size} viewBox="0 0 120 120" fill="none" className="-rotate-90">
        <circle cx="60" cy="60" r={R} stroke="#1f2937" strokeWidth={strokeWidth} />
        <circle
          cx="60"
          cy="60"
          r={R}
          stroke={color}
          strokeWidth={strokeWidth}
          strokeLinecap="round"
          strokeDasharray={CIRC}
          strokeDashoffset={offset}
          style={{ transition: "stroke-dashoffset 600ms ease, stroke 400ms ease" }}
        />
      </svg>
      <div className="absolute flex flex-col items-center">
        <span className="text-2xl font-bold text-text-primary">{pct}%</span>
        {label && <span className="text-xs text-text-muted">{label}</span>}
      </div>
    </div>
  );
}
