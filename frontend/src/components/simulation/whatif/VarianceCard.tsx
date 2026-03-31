import { ArrowDown, ArrowUp } from "lucide-react";

interface VarianceCardProps {
  label: string;
  original: number;
  branch: number;
  betterLabel: string;
  worseLabel: string;
  isBetter: boolean;
}

export default function VarianceCard({
  label,
  original,
  branch,
  betterLabel,
  worseLabel,
  isBetter,
}: VarianceCardProps) {
  const indicatorColor = isBetter ? "#22c55e" : "#ef4444";
  const Arrow = isBetter ? ArrowDown : ArrowUp;

  return (
    <div
      style={{
        background: "var(--bg-tertiary)",
        border: "1px solid var(--border-secondary)",
        borderRadius: 8,
        padding: 16,
        display: "flex",
        flexDirection: "column",
        gap: 6,
      }}
    >
      <div style={{ fontSize: 10, color: "var(--text-muted)", fontWeight: 600, textTransform: "uppercase" as const, letterSpacing: "0.04em" }}>
        {label}
      </div>
      <div style={{ display: "flex", gap: 12, alignItems: "baseline" }}>
        <div>
          <div style={{ fontSize: 10, color: "var(--text-muted)" }}>원본</div>
          <div style={{ fontSize: 16, fontWeight: 700, color: "var(--text-primary)", fontVariantNumeric: "tabular-nums" }}>
            {original.toFixed(4)}
          </div>
        </div>
        <div>
          <div style={{ fontSize: 10, color: "var(--text-muted)" }}>분기</div>
          <div style={{ fontSize: 16, fontWeight: 700, color: "var(--text-primary)", fontVariantNumeric: "tabular-nums" }}>
            {branch.toFixed(4)}
          </div>
        </div>
      </div>
      <div style={{ display: "flex", alignItems: "center", gap: 4, fontSize: 10, color: indicatorColor }}>
        <Arrow size={10} />
        {isBetter ? betterLabel : worseLabel}
      </div>
    </div>
  );
}
