"use client";

import type { LiveStats as LiveStatsType } from "@/types/simulation";

interface Props {
  stats: LiveStatsType | null;
}

export default function LiveStats({ stats }: Props) {
  if (!stats) {
    return (
      <div
        style={{
          border: "1px solid var(--border-secondary)",
          borderRadius: 6,
          padding: 10,
          color: "var(--text-muted)",
          fontSize: 12,
          background: "var(--bg-secondary)",
        }}
      >
        실시간 통계 대기 중...
      </div>
    );
  }

  const totalRounds = stats.total_rounds || 1;
  const percent = Math.max(0, Math.min(100, Math.round(stats.progress_percent)));
  const currentRound = Math.min(stats.current_round, totalRounds);

  return (
    <div
      style={{
        border: "1px solid var(--border-secondary)",
        borderRadius: 6,
        padding: 10,
        background: "var(--bg-secondary)",
        display: "flex",
        flexDirection: "column",
        gap: 8,
      }}
    >
      <div style={{ fontSize: 12, color: "var(--text-primary)", fontWeight: 600 }}>
        라운드 {currentRound}/{totalRounds} ({percent}%)
      </div>

      <div
        style={{
          height: 7,
          borderRadius: 999,
          background: "var(--border-secondary)",
          overflow: "hidden",
        }}
      >
        <div
          style={{
            width: `${percent}%`,
            height: "100%",
            background: "var(--accent-cyan)",
            transition: "width 0.3s ease",
          }}
        />
      </div>

      <div style={{ fontSize: 12, color: "var(--text-muted)", display: "flex", justifyContent: "space-between" }}>
        <span>총 액션</span>
        <span style={{ color: "var(--text-primary)", fontWeight: 600 }}>{stats.total_actions_count}</span>
      </div>
    </div>
  );
}
