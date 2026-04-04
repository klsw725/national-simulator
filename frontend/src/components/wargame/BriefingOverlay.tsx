"use client";

import type { RoundBriefing } from "@/types/simulation";

interface BriefingOverlayProps {
  briefing: RoundBriefing;
  round: number;
  onProceedToDecision: () => void;
}

const SEVERITY_META = {
  critical: { emoji: "🔴", cls: "text-red-400" },
  high: { emoji: "🟠", cls: "text-orange-400" },
  medium: { emoji: "🟡", cls: "text-yellow-400" },
  low: { emoji: "🔵", cls: "text-blue-400" },
} as const;

const DELTA_META: Record<string, { label: string; barCls: string }> = {
  tension: { label: "긴장도", barCls: "bg-red-400" },
  threat_perception: { label: "위협 인식", barCls: "bg-red-400" },
  domestic_pressure: { label: "국내 압력", barCls: "bg-amber-400" },
  resource_level: { label: "자원 수준", barCls: "bg-emerald-400" },
};

function deltaIndicator(val: number): { arrow: string; cls: string } {
  if (val > 0.005) return { arrow: "↑", cls: "text-red-400" };
  if (val < -0.005) return { arrow: "↓", cls: "text-emerald-400" };
  return { arrow: "→", cls: "text-[var(--text-muted)]" };
}

export default function BriefingOverlay({
  briefing,
  round,
  onProceedToDecision,
}: BriefingOverlayProps) {
  const hasDeltas = Object.keys(briefing.state_deltas).length > 0;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center pointer-events-auto">
      <div className="absolute inset-0 bg-black/60 backdrop-blur-[2px]" />

      <div className="relative w-full max-w-[600px] mx-4 max-h-[85vh] flex flex-col rounded-lg border border-[var(--border-secondary)] bg-[var(--bg-tertiary)] shadow-2xl">
        <div className="shrink-0 px-5 py-3.5 border-b border-[var(--border-secondary)] flex items-center gap-2.5">
          <span className="text-base leading-none">📋</span>
          <span className="text-sm font-bold text-[var(--text-primary)] tracking-wide font-mono">
            ROUND {round} 브리핑
          </span>
        </div>

        <div className="flex-1 overflow-y-auto px-5 py-4 flex flex-col gap-5">
          <section>
            <SectionHeader>핵심 이벤트</SectionHeader>
            <div className="flex flex-col gap-2.5 mt-2.5">
              {briefing.key_events.map((ev, i) => {
                const sev =
                  SEVERITY_META[ev.severity as keyof typeof SEVERITY_META] ??
                  SEVERITY_META.low;
                return (
                  <div key={i} className="flex items-start gap-2.5">
                    <span className="text-xs leading-5 shrink-0">{sev.emoji}</span>
                    <div className="flex-1 min-w-0">
                      <span
                        className={`text-[10px] font-bold uppercase tracking-wider ${sev.cls}`}
                      >
                        {ev.type}
                      </span>
                      <p className="text-xs text-[var(--text-primary)] leading-relaxed mt-0.5">
                        {ev.description}
                      </p>
                    </div>
                  </div>
                );
              })}
              {briefing.key_events.length === 0 && (
                <p className="text-xs text-[var(--text-muted)] italic">
                  이 라운드에 주요 이벤트 없음
                </p>
              )}
            </div>
          </section>

          {hasDeltas && (
            <section>
              <SectionHeader>상태 변화 (vs 이전 라운드)</SectionHeader>
              <div className="flex flex-col gap-2 mt-2.5">
                {Object.entries(briefing.state_deltas).map(([key, delta]) => {
                  const meta = DELTA_META[key] ?? {
                    label: key,
                    barCls: "bg-gray-400",
                  };
                  const indicator = deltaIndicator(delta);
                  const barWidth = Math.min(
                    100,
                    Math.round(Math.abs(delta) * 400),
                  );

                  return (
                    <div key={key} className="flex items-center gap-3">
                      <span className="text-[11px] text-[var(--text-muted)] w-16 shrink-0 truncate">
                        {meta.label}
                      </span>
                      <div className="flex-1 h-1.5 rounded-full bg-[var(--border-secondary)] overflow-hidden">
                        <div
                          className={`h-full rounded-full transition-all duration-500 ${meta.barCls}`}
                          style={{ width: `${barWidth}%` }}
                        />
                      </div>
                      <span
                        className={`text-[11px] font-mono font-bold w-16 text-right shrink-0 ${indicator.cls}`}
                      >
                        {indicator.arrow}{" "}
                        {delta > 0 ? "+" : ""}
                        {(delta * 100).toFixed(0)}%
                      </span>
                    </div>
                  );
                })}
              </div>
            </section>
          )}

          {briefing.previous_decision_outcome && (
            <section>
              <SectionHeader>지난 결정 결과</SectionHeader>
              <div className="mt-2 px-3.5 py-2.5 rounded border border-[var(--border-secondary)] bg-[var(--bg-primary)]">
                <p className="text-xs text-[var(--text-primary)] leading-relaxed">
                  {briefing.previous_decision_outcome}
                </p>
              </div>
            </section>
          )}

          <section>
            <SectionHeader>OSINT 정보 요약</SectionHeader>
            <div className="mt-2 flex flex-col gap-2">
              <span className="text-xs text-[var(--text-muted)]">
                관측 이벤트{" "}
                <span className="font-bold font-mono text-[var(--accent-cyan)]">
                  {briefing.social_media_summary?.total_posts ?? 0}
                </span>
                건
              </span>
              {(briefing.social_media_summary?.top_topics?.length ?? 0) > 0 && (
                <div className="flex flex-wrap gap-1.5">
                  {briefing.social_media_summary.top_topics.map((topic, i) => (
                    <span
                      key={i}
                      className="text-[10px] font-semibold px-2 py-0.5 rounded-full bg-[rgba(34,211,238,0.1)] text-[var(--accent-cyan)]"
                    >
                      {topic}
                    </span>
                  ))}
                </div>
              )}
            </div>
          </section>
        </div>

        <div className="shrink-0 px-5 py-4 border-t border-[var(--border-secondary)]">
          <button
            onClick={onProceedToDecision}
            className="w-full py-2.5 rounded-md text-sm font-bold tracking-wide cursor-pointer transition-colors duration-150 bg-amber-500/90 text-black hover:bg-amber-400"
          >
            브리핑 확인 → 결정 단계로
          </button>
        </div>
      </div>
    </div>
  );
}

function SectionHeader({ children }: { children: React.ReactNode }) {
  return (
    <h3 className="text-[10px] font-bold text-[var(--text-muted)] uppercase tracking-widest">
      {children}
    </h3>
  );
}
