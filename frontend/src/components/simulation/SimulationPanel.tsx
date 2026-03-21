"use client";

import { useState } from "react";
import { X, AlertTriangle } from "lucide-react";
import type { UseSimulationReturn } from "@/hooks/useSimulation";
import ScenarioForm from "./ScenarioForm";
import PipelineProgress from "./PipelineProgress";
import CheckpointReview from "./CheckpointReview";
import ScenarioList from "./ScenarioList";
import SimulationTimeline from "./SimulationTimeline";
import ReportViewer from "./ReportViewer";
import IntermediateResults from "./IntermediateResults";
import GraphTab from "./GraphTab";

type Tab = "create" | "progress" | "list" | "graph" | "timeline" | "report";

interface Props {
  open: boolean;
  onClose: () => void;
  sim: UseSimulationReturn;
}

export default function SimulationPanel({ open, onClose, sim }: Props) {
  const [tab, setTab] = useState<Tab>("create");

  if (!open) return null;

  const isCompleted = sim.pipelineStatus?.status === "completed";
  const hasCheckpoint = sim.checkpointData !== null;

  const showGraphTab = sim.pipelineStatus != null && [
    "simulating:prepare", "simulating:running", "simulating:report",
    "checkpoint:profiles", "checkpoint:config", "checkpoint:geopolitics",
    "completed"
  ].includes(sim.pipelineStatus.status);

  const tabs: { key: Tab; label: string; show: boolean }[] = [
    { key: "create", label: "새 시나리오", show: true },
    { key: "progress", label: "진행 상태", show: true },
    { key: "list", label: "목록", show: true },
    { key: "graph", label: "그래프", show: showGraphTab },
    { key: "timeline", label: "타임라인", show: isCompleted },
    { key: "report", label: "리포트", show: isCompleted },
  ];

  const visibleTabs = tabs.filter((t) => t.show);

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
        {visibleTabs.map((t) => (
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

        {tab === "progress" && (
          hasCheckpoint ? (
            <CheckpointReview
              checkpointData={sim.checkpointData!}
              onContinue={sim.continueCheckpoint}
              onCancel={() => setTab("list")}
            />
          ) : sim.pipelineStatus?.status?.startsWith("simulating:") ? (
            <div style={{ display: "flex", flexDirection: "column", height: "100%" }}>
              <PipelineProgress pipelineStatus={sim.pipelineStatus} onReview={() => {}} />
              <div style={{ flex: 1, minHeight: 0, marginTop: 12 }}>
                <IntermediateResults
                  pipelineStatus={sim.pipelineStatus.status}
                  scenarioId={sim.activeScenario?.id ?? null}
                />
              </div>
            </div>
          ) : (
            <PipelineProgress
              pipelineStatus={sim.pipelineStatus}
              onReview={() => {
                if (hasCheckpoint) setTab("progress");
              }}
            />
          )
        )}

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

        {tab === "timeline" && (
          <SimulationTimeline actions={sim.simulationResults} />
        )}

        {tab === "graph" && sim.activeScenario && (
          <GraphTab scenarioId={sim.activeScenario.id} />
        )}

        {tab === "report" && (
          <ReportViewer markdown={sim.reportMarkdown} />
        )}
      </div>
    </div>
  );
}
