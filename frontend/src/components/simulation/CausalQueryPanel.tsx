"use client";

import { useState, useCallback } from "react";
import { RefreshCw } from "lucide-react";
import { fitCausalModel } from "@/lib/gatewayApi";
import { STATE_VARIABLES, type ModelInfo } from "./causal/shared";
import InterventionTab from "./causal/InterventionTab";
import CounterfactualTab from "./causal/CounterfactualTab";
import AttributionTab from "./causal/AttributionTab";

interface Props {
  scenarioId: string;
}

type QueryTab = "intervention" | "counterfactual" | "attribution";

export default function CausalQueryPanel({ scenarioId }: Props) {
  const [activeTab, setActiveTab] = useState<QueryTab>("intervention");
  const [modelId, setModelId] = useState<string | null>(null);
  const [modelVars, setModelVars] = useState<string[]>(STATE_VARIABLES);
  const [fitting, setFitting] = useState(false);
  const [fitError, setFitError] = useState<string | null>(null);
  const [queryError, setQueryError] = useState<string | null>(null);

  const vars = modelVars.length > 0 ? modelVars : STATE_VARIABLES;

  const ensureModel = useCallback(async (): Promise<ModelInfo | null> => {
    if (modelId) return { id: modelId, vars: modelVars };
    setFitting(true);
    setFitError(null);
    try {
      const id = `model_${scenarioId}_${Date.now()}`;
      const res = await fitCausalModel(id, scenarioId);
      const fittedVars = res.variables?.length ? res.variables : vars;
      setModelId(id);
      setModelVars(fittedVars);
      return { id, vars: fittedVars };
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err);
      const detail = msg.match(/"detail"\s*:\s*"([^"]+)"/)?.[1];
      setFitError(detail ?? "모델 피팅 실패");
      return null;
    } finally {
      setFitting(false);
    }
  }, [modelId, modelVars, scenarioId, vars]);

  const tabs: { key: QueryTab; label: string }[] = [
    { key: "intervention", label: "개입" },
    { key: "counterfactual", label: "반사실" },
    { key: "attribution", label: "귀속" },
  ];

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
            <InterventionTab
              key={modelId ?? "none"}
              vars={vars}
              queryError={queryError}
              setQueryError={setQueryError}
              ensureModel={ensureModel}
              fitting={fitting}
            />
          )}

          {activeTab === "counterfactual" && (
            <CounterfactualTab
              key={modelId ?? "none"}
              vars={vars}
              queryError={queryError}
              setQueryError={setQueryError}
              ensureModel={ensureModel}
              fitting={fitting}
            />
          )}

          {activeTab === "attribution" && (
            <AttributionTab
              key={modelId ?? "none"}
              vars={vars}
              queryError={queryError}
              setQueryError={setQueryError}
              ensureModel={ensureModel}
              fitting={fitting}
            />
          )}

          {modelId && (
            <div style={{ marginTop: 12, display: "flex", justifyContent: "flex-end" }}>
              <button
                onClick={() => { setModelId(null); setModelVars(STATE_VARIABLES); }}
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
                <RefreshCw size={10} aria-hidden="true" />
                모델 재설정
              </button>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
