"use client";

import { useCallback, useEffect, useState } from "react";
import * as api from "@/lib/gatewayApi";

type DashboardData = Awaited<ReturnType<typeof api.getDashboard>>;

export default function AnalystDashboard() {
  const [data, setData] = useState<DashboardData | null>(null);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    try {
      const result = await api.getDashboard();
      setData(result);
    } catch {}
    setLoading(false);
  }, []);

  useEffect(() => {
    load();
    const timer = setInterval(load, 30_000);
    return () => clearInterval(timer);
  }, [load]);

  if (loading) {
    return (
      <div style={{ padding: 24, color: "rgb(107, 114, 128)", fontSize: 13, textAlign: "center" }}>
        불러오는 중...
      </div>
    );
  }

  if (!data) {
    return (
      <div style={{ padding: 24, color: "rgb(107, 114, 128)", fontSize: 13, textAlign: "center" }}>
        대시보드 데이터를 불러올 수 없습니다
      </div>
    );
  }

  return (
    <div style={{ padding: 16, display: "flex", flexDirection: "column", gap: 14 }}>
      <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
        <StatCard label="전체" value={data.total_scenarios} color="#f3f4f6" />
        <StatCard label="완료" value={data.by_status.completed ?? 0} color="#22c55e" />
        <StatCard label="실행 중" value={(data.by_status.starting ?? 0) + Object.entries(data.by_status).filter(([k]) => k.startsWith("simulating")).reduce((s, [, v]) => s + v, 0)} color="#22d3ee" />
        <StatCard label="실패" value={data.by_status.failed ?? 0} color="#ef4444" />
      </div>

      {Object.keys(data.by_region).length > 0 && (
        <Section title="지역별 분포">
          <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
            {Object.entries(data.by_region).map(([region, count]) => (
              <div key={region} style={{ display: "flex", justifyContent: "space-between", fontSize: 11 }}>
                <span style={{ color: "#d1d5db" }}>{region}</span>
                <span style={{ color: "rgb(107,114,128)", fontVariantNumeric: "tabular-nums" }}>{count}</span>
              </div>
            ))}
          </div>
        </Section>
      )}

      {data.running_simulations.length > 0 && (
        <Section title="실행 중인 시뮬레이션">
          <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
            {data.running_simulations.map((sim) => (
              <div key={sim.id} style={{ display: "flex", justifyContent: "space-between", fontSize: 11 }}>
                <span style={{ color: "#d1d5db", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap", flex: 1 }}>
                  {sim.name}
                </span>
                <span
                  style={{
                    fontSize: 10,
                    padding: "1px 6px",
                    borderRadius: 3,
                    background: "rgba(34, 211, 238, 0.1)",
                    color: "#22d3ee",
                    flexShrink: 0,
                    marginLeft: 8,
                  }}
                >
                  {sim.status}
                </span>
              </div>
            ))}
          </div>
        </Section>
      )}

      {data.recent_activity.length > 0 && (
        <Section title="최근 활동">
          <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
            {data.recent_activity.map((act, i) => (
              <div key={i} style={{ fontSize: 11, display: "flex", gap: 6 }}>
                <span style={{ color: "rgb(75,85,99)", fontVariantNumeric: "tabular-nums", flexShrink: 0 }}>
                  {act.timestamp.slice(11, 16)}
                </span>
                <span style={{ color: "rgb(107,114,128)" }}>{act.action}</span>
              </div>
            ))}
          </div>
        </Section>
      )}
    </div>
  );
}

function StatCard({ label, value, color }: { label: string; value: number; color: string }) {
  return (
    <div
      style={{
        flex: 1,
        minWidth: 70,
        background: "rgba(255,255,255,0.03)",
        border: "1px solid rgba(255,255,255,0.05)",
        borderRadius: 6,
        padding: "10px 12px",
        textAlign: "center",
      }}
    >
      <div style={{ fontSize: 20, fontWeight: 700, color, fontVariantNumeric: "tabular-nums" }}>
        {value}
      </div>
      <div style={{ fontSize: 10, color: "rgb(107,114,128)", marginTop: 2 }}>{label}</div>
    </div>
  );
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div>
      <div style={{ fontSize: 10, fontWeight: 600, color: "rgb(107,114,128)", textTransform: "uppercase", letterSpacing: "0.05em", marginBottom: 6 }}>
        {title}
      </div>
      {children}
    </div>
  );
}
