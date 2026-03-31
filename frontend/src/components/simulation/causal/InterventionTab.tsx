"use client";

import { useState } from "react";
import { Play, Loader2 } from "lucide-react";
import {
  causalIntervene,
  type CausalInterventionResult,
} from "@/lib/gatewayApi";
import { selectStyle, buttonStyle, type CausalTabProps } from "./shared";

export default function InterventionTab({ vars, setQueryError, ensureModel, fitting }: CausalTabProps) {
  const [intVar, setIntVar] = useState(vars[0]);
  const [intVal, setIntVal] = useState(0.5);
  const [intResult, setIntResult] = useState<CausalInterventionResult | null>(null);
  const [intLoading, setIntLoading] = useState(false);

  async function runIntervention() {
    setQueryError(null);
    setIntLoading(true);
    try {
      const model = await ensureModel();
      if (!model) return;
      const variable = model.vars.includes(intVar) ? intVar : model.vars[0];
      const res = await causalIntervene(model.id, { [variable]: intVal });
      setIntResult(res);
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err);
      const detail = msg.match(/"detail"\s*:\s*"([^"]+)"/)?.[1];
      setQueryError(detail ?? "개입 쿼리 실행 실패");
    } finally {
      setIntLoading(false);
    }
  }

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
      <div>
        <label style={{ fontSize: 10, color: "var(--text-muted)", display: "block", marginBottom: 4 }}>
          개입 변수
        </label>
        <select value={intVar} onChange={(e) => setIntVar(e.target.value)} style={selectStyle}>
          {vars.map((v) => (
            <option key={v} value={v}>{v}</option>
          ))}
        </select>
      </div>
      <div>
        <label style={{ fontSize: 10, color: "var(--text-muted)", display: "block", marginBottom: 4 }}>
          값: {intVal.toFixed(2)}
        </label>
        <input
          type="range"
          min={0}
          max={1}
          step={0.01}
          value={intVal}
          onChange={(e) => setIntVal(Number(e.target.value))}
          style={{ width: "100%", accentColor: "var(--accent-cyan)" }}
        />
      </div>
      <button onClick={runIntervention} disabled={intLoading || fitting} style={buttonStyle}>
        {intLoading ? <Loader2 size={12} style={{ animation: "spin 1s linear infinite" }} /> : <Play size={12} />}
        쿼리 실행
      </button>

      {intResult && (
        <div style={{ display: "flex", flexDirection: "column", gap: 8, marginTop: 4 }}>
          <div style={{ fontSize: 10, color: "var(--text-muted)" }}>
            샘플: {intResult.num_samples}
          </div>
          {Object.entries(intResult.targets).map(([key, val]) => (
            <div
              key={key}
              style={{
                background: "rgba(255,255,255,0.03)",
                border: "1px solid var(--border-secondary)",
                borderRadius: 6,
                padding: "8px 10px",
              }}
            >
              <div style={{ fontSize: 11, fontWeight: 600, color: "var(--text-primary)", marginBottom: 4 }}>
                {key}
              </div>
              <div style={{ display: "flex", gap: 12, fontSize: 10, color: "var(--text-muted)" }}>
                <span>평균: <b style={{ color: "var(--text-primary)" }}>{val.mean.toFixed(4)}</b></span>
                <span>표준편차: {val.std.toFixed(4)}</span>
                <span>CI: [{val.ci_lower.toFixed(3)}, {val.ci_upper.toFixed(3)}]</span>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
