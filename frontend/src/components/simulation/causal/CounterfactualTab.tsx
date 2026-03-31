"use client";

import { useState } from "react";
import { Play, Loader2 } from "lucide-react";
import {
  causalCounterfactual,
  type CausalCounterfactualResult,
} from "@/lib/gatewayApi";
import { inputStyle, selectStyle, buttonStyle, type CausalTabProps } from "./shared";

export default function CounterfactualTab({ vars, setQueryError, ensureModel, fitting }: CausalTabProps) {
  const [cfObserved, setCfObserved] = useState<Record<string, number>>(
    Object.fromEntries(vars.map((v) => [v, 0.5])),
  );
  const [cfIntVar, setCfIntVar] = useState(vars[0]);
  const [cfIntVal, setCfIntVal] = useState(0.8);
  const [cfResult, setCfResult] = useState<CausalCounterfactualResult | null>(null);
  const [cfLoading, setCfLoading] = useState(false);

  async function runCounterfactual() {
    setQueryError(null);
    setCfLoading(true);
    try {
      const model = await ensureModel();
      if (!model) return;
      const observed = Object.fromEntries(model.vars.map((v) => [v, cfObserved[v] ?? 0.5]));
      const variable = model.vars.includes(cfIntVar) ? cfIntVar : model.vars[0];
      const res = await causalCounterfactual(model.id, observed, { [variable]: cfIntVal });
      setCfResult(res);
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err);
      const detail = msg.match(/"detail"\s*:\s*"([^"]+)"/)?.[1];
      setQueryError(detail ?? "반사실 쿼리 실행 실패");
    } finally {
      setCfLoading(false);
    }
  }

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
      <div style={{ fontSize: 10, color: "var(--text-muted)", fontWeight: 600, marginBottom: 2 }}>
        관측값
      </div>
      {vars.map((v) => (
        <div key={v} style={{ display: "flex", alignItems: "center", gap: 8 }}>
          <span style={{ fontSize: 11, color: "var(--text-muted)", width: 120, flexShrink: 0 }}>{v}</span>
          <input
            type="number"
            min={0}
            max={1}
            step={0.1}
            value={cfObserved[v] ?? 0.5}
            onChange={(e) => setCfObserved((prev) => ({ ...prev, [v]: Number(e.target.value) }))}
            style={{ ...inputStyle, width: 70 }}
          />
        </div>
      ))}
      <div style={{ borderTop: "1px solid var(--border-secondary)", paddingTop: 12 }}>
        <div style={{ fontSize: 10, color: "var(--text-muted)", fontWeight: 600, marginBottom: 8 }}>
          반사실 개입
        </div>
        <div style={{ display: "flex", gap: 8 }}>
          <select value={cfIntVar} onChange={(e) => setCfIntVar(e.target.value)} style={{ ...selectStyle, flex: 1 }}>
            {vars.map((v) => (
              <option key={v} value={v}>{v}</option>
            ))}
          </select>
          <input
            type="number"
            min={0}
            max={1}
            step={0.1}
            value={cfIntVal}
            onChange={(e) => setCfIntVal(Number(e.target.value))}
            style={{ ...inputStyle, width: 70 }}
          />
        </div>
      </div>
      <button onClick={runCounterfactual} disabled={cfLoading || fitting} style={buttonStyle}>
        {cfLoading ? <Loader2 size={12} style={{ animation: "spin 1s linear infinite" }} /> : <Play size={12} />}
        쿼리 실행
      </button>

      {cfResult && (
        <div style={{ display: "flex", flexDirection: "column", gap: 6, marginTop: 4 }}>
          {Object.entries(cfResult.differences).map(([key, diff]) => (
            <div
              key={key}
              style={{
                background: "rgba(255,255,255,0.03)",
                border: "1px solid var(--border-secondary)",
                borderRadius: 6,
                padding: "8px 10px",
                display: "flex",
                justifyContent: "space-between",
                alignItems: "center",
              }}
            >
              <span style={{ fontSize: 11, color: "var(--text-primary)" }}>{key}</span>
              <div style={{ display: "flex", gap: 12, fontSize: 10, color: "var(--text-muted)" }}>
                <span>{cfResult.observed[key]?.toFixed(3)} → {cfResult.counterfactual[key]?.toFixed(3)}</span>
                <span style={{ color: diff > 0 ? "#22c55e" : diff < 0 ? "#ef4444" : "var(--text-muted)", fontWeight: 600 }}>
                  {diff > 0 ? "+" : ""}{diff.toFixed(3)}
                </span>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
