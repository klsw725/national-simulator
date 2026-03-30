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
import { Play, RefreshCw, Loader2 } from "lucide-react";
import {
  causalIntervene,
  causalCounterfactual,
  causalAttribute,
  fitCausalModel,
  type CausalInterventionResult,
  type CausalCounterfactualResult,
  type CausalAttributionResult,
} from "@/lib/gatewayApi";

interface Props {
  scenarioId: string;
}

type QueryTab = "intervention" | "counterfactual" | "attribution";

const STATE_VARIABLES = ["threat_perception", "domestic_pressure", "resource_level"];
const ATTRIBUTION_COLORS = ["#3b82f6", "#8b5cf6", "#f97316", "#22c55e", "#ef4444", "#06b6d4"];

const inputStyle: React.CSSProperties = {
  width: "100%",
  padding: "6px 8px",
  background: "rgba(255,255,255,0.04)",
  border: "1px solid var(--border-secondary)",
  borderRadius: 4,
  color: "var(--text-primary)",
  fontSize: 12,
  outline: "none",
};

const selectStyle: React.CSSProperties = {
  ...inputStyle,
  appearance: "none" as const,
  cursor: "pointer",
};

const buttonStyle: React.CSSProperties = {
  padding: "8px 14px",
  background: "var(--accent-cyan)",
  border: "none",
  borderRadius: 4,
  color: "var(--bg-primary)",
  fontSize: 12,
  fontWeight: 700,
  cursor: "pointer",
  display: "inline-flex",
  alignItems: "center",
  gap: 6,
};

export default function CausalQueryPanel({ scenarioId }: Props) {
  const [activeTab, setActiveTab] = useState<QueryTab>("intervention");
  const [modelId, setModelId] = useState<string | null>(null);
  const [modelVars, setModelVars] = useState<string[]>(STATE_VARIABLES);
  const [fitting, setFitting] = useState(false);
  const [fitError, setFitError] = useState<string | null>(null);

  const vars = modelVars.length > 0 ? modelVars : STATE_VARIABLES;

  const [intVar, setIntVar] = useState(STATE_VARIABLES[0]);
  const [intVal, setIntVal] = useState(0.5);
  const [intResult, setIntResult] = useState<CausalInterventionResult | null>(null);
  const [intLoading, setIntLoading] = useState(false);

  const [cfObserved, setCfObserved] = useState<Record<string, number>>(
    Object.fromEntries(STATE_VARIABLES.map((v) => [v, 0.5])),
  );
  const [cfIntVar, setCfIntVar] = useState(STATE_VARIABLES[0]);
  const [cfIntVal, setCfIntVal] = useState(0.8);
  const [cfResult, setCfResult] = useState<CausalCounterfactualResult | null>(null);
  const [cfLoading, setCfLoading] = useState(false);

  const [attrTarget, setAttrTarget] = useState(STATE_VARIABLES[0]);
  const [attrResult, setAttrResult] = useState<CausalAttributionResult | null>(null);
  const [attrLoading, setAttrLoading] = useState(false);

  const [queryError, setQueryError] = useState<string | null>(null);

  interface ModelInfo { id: string; vars: string[] }

  async function ensureModel(): Promise<ModelInfo | null> {
    if (modelId) return { id: modelId, vars: modelVars };
    setFitting(true);
    setFitError(null);
    try {
      const id = `model_${scenarioId}_${Date.now()}`;
      const res = await fitCausalModel(id, scenarioId);
      const fittedVars = res.variables?.length ? res.variables : vars;
      setModelId(id);
      setModelVars(fittedVars);
      setIntVar(fittedVars[0]);
      setCfIntVar(fittedVars[0]);
      setAttrTarget(fittedVars[0]);
      setCfObserved(Object.fromEntries(fittedVars.map((v: string) => [v, 0.5])));
      return { id, vars: fittedVars };
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err);
      const detail = msg.match(/"detail"\s*:\s*"([^"]+)"/)?.[1];
      setFitError(detail ?? "모델 피팅 실패");
      return null;
    } finally {
      setFitting(false);
    }
  }

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

  const tabs: { key: QueryTab; label: string }[] = [
    { key: "intervention", label: "개입" },
    { key: "counterfactual", label: "반사실" },
    { key: "attribution", label: "귀속" },
  ];

  const isAnyLoading = intLoading || cfLoading || attrLoading || fitting;

  return (
    <div>
      <div
        style={{
          fontSize: 11,
          fontWeight: 600,
          color: "var(--text-muted)",
          textTransform: "uppercase" as const,
          letterSpacing: "0.05em",
          marginBottom: 8,
        }}
      >
        Causal Query
      </div>

      <div
        style={{
          background: "var(--bg-tertiary)",
          border: "1px solid var(--border-secondary)",
          borderRadius: 8,
          overflow: "hidden",
        }}
      >
        <div style={{ display: "flex", borderBottom: "1px solid var(--border-secondary)" }}>
          {tabs.map((t) => (
            <button
              key={t.key}
              onClick={() => setActiveTab(t.key)}
              style={{
                flex: 1,
                padding: "8px 0",
                background: "transparent",
                border: "none",
                borderBottom: `2px solid ${activeTab === t.key ? "var(--accent-cyan)" : "transparent"}`,
                color: activeTab === t.key ? "var(--accent-cyan)" : "var(--text-muted)",
                fontSize: 11,
                fontWeight: activeTab === t.key ? 600 : 400,
                cursor: "pointer",
              }}
            >
              {t.label}
            </button>
          ))}
        </div>

        <div style={{ padding: 14 }}>
          {(fitError || queryError) && (
            <div
              style={{
                padding: "6px 10px",
                marginBottom: 12,
                background: "rgba(239, 68, 68, 0.1)",
                border: "1px solid rgba(239, 68, 68, 0.25)",
                borderRadius: 4,
                fontSize: 11,
                color: "#ef4444",
              }}
            >
              {fitError || queryError}
            </div>
          )}

          {activeTab === "intervention" && (
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
              <button onClick={runIntervention} disabled={isAnyLoading} style={buttonStyle}>
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
          )}

          {activeTab === "counterfactual" && (
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
              <button onClick={runCounterfactual} disabled={isAnyLoading} style={buttonStyle}>
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
          )}

          {activeTab === "attribution" && (
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
              <button onClick={runAttribution} disabled={isAnyLoading} style={buttonStyle}>
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
          )}

          {modelId && (
            <div style={{ marginTop: 12, display: "flex", justifyContent: "flex-end" }}>
              <button
                onClick={() => { setModelId(null); setModelVars(STATE_VARIABLES); setIntResult(null); setCfResult(null); setAttrResult(null); }}
                style={{
                  background: "transparent",
                  border: "none",
                  color: "var(--text-muted)",
                  fontSize: 10,
                  cursor: "pointer",
                  display: "inline-flex",
                  alignItems: "center",
                  gap: 4,
                }}
              >
                <RefreshCw size={10} />
                모델 재설정
              </button>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
