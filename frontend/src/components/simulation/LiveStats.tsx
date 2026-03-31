"use client";

import { memo } from "react";
import type { LiveStats as LiveStatsType } from "@/types/simulation";

interface Props {
  stats: LiveStatsType | null;
}

function LiveStats({ stats }: Props) {
  if (!stats) {
    return (
      <div className="border border-[var(--border-secondary)] rounded-md p-2.5 text-[var(--text-muted)] text-xs bg-[var(--bg-secondary)]">
        실시간 통계 대기 중...
      </div>
    );
  }

  const totalRounds = stats.total_rounds || 1;
  const percent = Math.max(0, Math.min(100, Math.round(stats.progress_percent)));
  const currentRound = Math.min(stats.current_round, totalRounds);

  return (
    <div
      aria-live="polite"
      className="border border-[var(--border-secondary)] rounded-md p-2.5 bg-[var(--bg-secondary)] flex flex-col gap-2"
    >
      <div className="text-xs text-[var(--text-primary)] font-semibold">
        라운드 {currentRound}/{totalRounds} ({percent}%)
      </div>

      <div className="h-[7px] rounded-full bg-[var(--border-secondary)] overflow-hidden">
        <div
          className="h-full bg-[var(--accent-cyan)] transition-[width] duration-300"
          style={{ width: `${percent}%` }}
        />
      </div>

      <div className="text-xs text-[var(--text-muted)] flex justify-between">
        <span>총 액션</span>
        <span className="text-[var(--text-primary)] font-semibold">{stats.total_actions_count}</span>
      </div>
    </div>
  );
}

export default memo(LiveStats);
