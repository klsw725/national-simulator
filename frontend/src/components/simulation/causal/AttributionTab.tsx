"use client";

import { useState } from "react";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  Cell,
} from "recharts";
import { Play, Loader2 } from "lucide-react";
import {
  causalAttribute,
  type CausalAttributionResult,
} from "@/lib/gatewayApi";
import { ATTRIBUTION_COLORS, selectStyle, buttonStyle, type CausalTabProps } from "./shared";

export default function AttributionTab({ vars, setQueryError, ensureModel, fitting }: CausalTabProps) {
  const [attrTarget, setAttrTarget] = useState(vars[0]);
  const [attrResult, setAttrResult] = useState<CausalAttributionResult | null>(null);
  const [attrLoading, setAttrLoading] = useState(false);

  async function runAttribution() {
    setQueryError(null);
    setAttrLoading(true);
    try {
      const model = await ensureModel();
      if (!model) return;
      const target = model.vars.includes(attrTarget) ? attrTarget : model.vars[0];
      const res = await causalAttribute(model.id, target);
      setAttrResult(res);
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err);
      const detail = msg.match(/"detail"\s*:\s*"([^"]+)"/)?.[1];
      setQueryError(detail ?? "귀속 쿼리 실행 실패");
    } finally {
      setAttrLoading(false);
    }
  }

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
      <div>
        <label style={{ fontSize: 10, color: "var(--text-muted)", display: "block", marginBottom: 4 }}>
          대상 변수
        </label>
        <select value={attrTarget} onChange={(e) => setAttrTarget(e.target.value)} style={selectStyle}>
          {vars.map((v) => (
            <option key={v} value={v}>{v}</option>
          ))}
        </select>
      </div>
      <button onClick={runAttribution} disabled={attrLoading || fitting} style={buttonStyle}>
        {attrLoading ? <Loader2 size={12} style={{ animation: "spin 1s linear infinite" }} /> : <Play size={12} />}
        귀속 분석
      </button>

      {attrResult && (
        <div style={{ marginTop: 4 }}>
          <div style={{ fontSize: 10, color: "var(--text-muted)", marginBottom: 6 }}>
            방법: {attrResult.method} · 총 설명률: {(attrResult.total_explained * 100).toFixed(1)}%
          </div>
          <div style={{ height: 180 }}>
            <ResponsiveContainer width="100%" height="100%">
              <BarChart
                data={Object.entries(attrResult.attributions).map(([name, value]) => ({ name, value }))}
                layout="vertical"
                margin={{ top: 0, right: 8, left: 8, bottom: 0 }}
              >
                <XAxis
                  type="number"
                  tick={{ fill: "#9ca3af", fontSize: 9 }}
                  tickLine={false}
                  axisLine={false}
                />
                <YAxis
                  type="category"
                  dataKey="name"
                  tick={{ fill: "#d1d5db", fontSize: 10 }}
                  tickLine={false}
                  axisLine={false}
                  width={100}
                />
                <Tooltip
                  contentStyle={{
                    background: "var(--bg-secondary)",
                    border: "1px solid var(--border-secondary)",
                    borderRadius: 6,
                    fontSize: 11,
                    color: "var(--text-primary)",
                  }}
                  formatter={(value) => [`${(Number(value) * 100).toFixed(1)}%`, "기여도"]}
                />
                <Bar dataKey="value" radius={[0, 4, 4, 0]}>
                  {Object.keys(attrResult.attributions).map((_, i) => (
                    <Cell key={i} fill={ATTRIBUTION_COLORS[i % ATTRIBUTION_COLORS.length]} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>
      )}
    </div>
  );
}
