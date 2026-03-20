"use client";

import { useState } from "react";
import { X, AlertTriangle } from "lucide-react";
import { useSimulation } from "@/hooks/useSimulation";
import ScenarioForm from "./ScenarioForm";
import PipelineProgress from "./PipelineProgress";
import ScenarioList from "./ScenarioList";

type Tab = "create" | "progress" | "list";

const TABS: { key: Tab; label: string }[] = [
  { key: "create", label: "새 시나리오" },
  { key: "progress", label: "진행 상태" },
  { key: "list", label: "시나리오 목록" },
];

interface Props {
  open: boolean;
  onClose: () => void;
}

export default function SimulationPanel({ open, onClose }: Props) {
  const [tab, setTab] = useState<Tab>("create");
  const sim = useSimulation();

  if (!open) return null;

  return (
    <div
      style={{
        position: "fixed",
        top: 0,
        right: 0,
        width: 400,
        height: "100vh",
        background: "var(--bg-secondary)",
        borderLeft: "1px solid var(--border-secondary)",
        display: "flex",
        flexDirection: "column",
        zIndex: 20,
        transition: "transform 0.2s ease",
      }}
    >
      {/* Header */}
      <div
        style={{
          padding: "14px 16px",
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          borderBottom: "1px solid var(--border-secondary)",
          flexShrink: 0,
        }}
      >
        <span
          style={{
            fontSize: 14,
            fontWeight: 700,
            color: "var(--text-primary)",
            letterSpacing: "0.02em",
          }}
        >
          SIMULATION
        </span>
        <button
          onClick={onClose}
          style={{
            background: "transparent",
            border: "none",
            padding: 4,
            cursor: "pointer",
            color: "var(--text-muted)",
            display: "flex",
            alignItems: "center",
          }}
        >
          <X size={18} />
        </button>
      </div>

      {/* Tabs */}
      <div
        style={{
          display: "flex",
          borderBottom: "1px solid var(--border-secondary)",
          flexShrink: 0,
        }}
      >
        {TABS.map((t) => (
          <button
            key={t.key}
            onClick={() => setTab(t.key)}
            style={{
              flex: 1,
              padding: "10px 0",
              background: "transparent",
              border: "none",
              borderBottom: `2px solid ${tab === t.key ? "var(--accent-cyan)" : "transparent"}`,
              color: tab === t.key ? "var(--accent-cyan)" : "var(--text-muted)",
              fontSize: 12,
              fontWeight: tab === t.key ? 600 : 400,
              cursor: "pointer",
              transition: "color 0.15s, border-color 0.15s",
            }}
          >
            {t.label}
          </button>
        ))}
      </div>

      {/* Error banner */}
      {sim.error && (
        <div
          style={{
            margin: "12px 16px 0",
            padding: "8px 12px",
            background: "rgba(239, 68, 68, 0.1)",
            border: "1px solid rgba(239, 68, 68, 0.25)",
            borderRadius: 4,
            display: "flex",
            alignItems: "flex-start",
            gap: 8,
            flexShrink: 0,
          }}
        >
          <AlertTriangle size={14} color="var(--accent-red)" style={{ marginTop: 1, flexShrink: 0 }} />
          <div style={{ fontSize: 12, color: "var(--accent-red)", lineHeight: 1.4 }}>
            {sim.error}
          </div>
          <button
            onClick={sim.clearError}
            style={{
              background: "transparent",
              border: "none",
              color: "var(--accent-red)",
              cursor: "pointer",
              padding: 0,
              marginLeft: "auto",
              flexShrink: 0,
            }}
          >
            <X size={12} />
          </button>
        </div>
      )}

      {/* Content */}
      <div
        style={{
          flex: 1,
          overflow: "auto",
          padding: 16,
        }}
      >
        {tab === "create" && (
          <ScenarioForm
            onSubmit={async (data) => {
              await sim.createAndRun(data);
              setTab("progress");
            }}
            isRunning={sim.isRunning}
          />
        )}

        {tab === "progress" && <PipelineProgress pipelineStatus={sim.pipelineStatus} />}

        {tab === "list" && (
          <ScenarioList
            scenarios={sim.scenarios}
            activeId={sim.activeScenario?.id ?? null}
            onSelect={(s) => {
              sim.selectScenario(s);
              setTab("progress");
            }}
            onDelete={sim.deleteScenario}
          />
        )}
      </div>
    </div>
  );
}
