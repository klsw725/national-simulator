"use client";

import { useMemo, useState } from "react";
import { X, AlertTriangle, RotateCcw } from "lucide-react";
import { retrySimulation } from "@/lib/gatewayApi";
import type { UseSimulationReturn } from "@/hooks/useSimulation";
import { useLiveSimulation } from "@/hooks/useLiveSimulation";
import ScenarioForm from "./ScenarioForm";
import PipelineProgress from "./PipelineProgress";
import CheckpointReview from "./CheckpointReview";
import ScenarioList from "./ScenarioList";
import SimulationTimeline from "./SimulationTimeline";
import ReportViewer from "./ReportViewer";
import IntermediateResults from "./IntermediateResults";
import GraphTab from "./GraphTab";
import DecisionPointView from "./DecisionPointView";
import GeopoliticsView from "./GeopoliticsView";
import HealthDashboard from "./HealthDashboard";
import ExportPanel from "./ExportPanel";
import ComparisonView from "./ComparisonView";
import AnalystDashboard from "./AnalystDashboard";
import ScenarioSearch from "./ScenarioSearch";
import ConversationPanel from "./ConversationPanel";
import WhatIfBranchView from "./WhatIfBranchView";
import CausalDAGView from "./CausalDAGView";
import CausalQueryPanel from "./CausalQueryPanel";
import WarRoom from "../wargame/WarRoom";

type Tab = "create" | "progress" | "what_if" | "decisions" | "list" | "graph" | "geopolitics" | "timeline" | "report" | "export" | "conversation" | "compare" | "dashboard" | "health" | "causal";

type TabGroup = "scenario" | "simulation" | "analysis" | "system";

const TAB_GROUPS: { key: TabGroup; label: string; tabs: Tab[] }[] = [
  { key: "scenario", label: "시나리오", tabs: ["create", "list", "compare"] },
  { key: "simulation", label: "시뮬레이션", tabs: ["progress", "what_if", "decisions", "report"] },
  { key: "analysis", label: "분석", tabs: ["graph", "geopolitics", "timeline", "causal", "export", "conversation"] },
  { key: "system", label: "시스템", tabs: ["dashboard", "health"] },
];

const getGroupForTab = (t: Tab): TabGroup => {
  for (const g of TAB_GROUPS) {
    if (g.tabs.includes(t)) return g.key;
  }
  return "scenario";
};

interface Props {
  open: boolean;
  onClose: () => void;
  sim: UseSimulationReturn;
  onOpenWhatIfCompare?: (branchId: string) => void;
  onFlyTo?: (lng: number, lat: number) => void;
  onWargameOverlay?: (lens: string | null, phase: string | null) => void;
}

export default function SimulationPanel({ open, onClose, sim, onOpenWhatIfCompare, onFlyTo, onWargameOverlay }: Props) {
  const [tab, setTab] = useState<Tab>("create");

  const isWargameMode = sim.activeScenario?.simulation_params?.wargame_enabled === true;
  const wargamePhaseActive =
    sim.pipelineStatus?.status?.startsWith("simulating:wargame") ||
    sim.pipelineStatus?.status?.startsWith("wargame:");
  const wargameCompleted = isWargameMode && sim.pipelineStatus?.status === "completed";

  const liveStatusForActions = useMemo(() => {
    if (isWargameMode && wargamePhaseActive) return "simulating:running";
    return sim.pipelineStatus?.status ?? null;
  }, [isWargameMode, wargamePhaseActive, sim.pipelineStatus?.status]);

  const live = useLiveSimulation(
    isWargameMode && wargamePhaseActive ? sim.activeScenario?.id ?? null : null,
    liveStatusForActions,
  );

  if (!open) return null;

  const analysisOrSystemTab = getGroupForTab(tab) === "analysis" || getGroupForTab(tab) === "system";
  if (isWargameMode && sim.activeScenario && (wargamePhaseActive || (wargameCompleted && tab !== "report" && !analysisOrSystemTab))) {
    return (
      <WarRoom
        scenarioId={sim.activeScenario.id}
        totalRounds={sim.activeScenario.simulation_params?.geopolitics_rounds ?? sim.activeScenario.max_rounds}
        actions={live.actions}
        onClose={onClose}
        onViewReport={() => setTab("report")}
        onCreateWhatIf={(round) => {
          onOpenWhatIfCompare?.(`whatif-round-${round}`);
        }}
        onWargameOverlay={onWargameOverlay}
      />
    );
  }

  const isCompleted = sim.pipelineStatus?.status === "completed";
  const hasCheckpoint = sim.checkpointData !== null;

  const showGraphTab = sim.pipelineStatus != null && [
    "simulating:prepare", "simulating:running", "simulating:report",
    "checkpoint:profiles", "checkpoint:config", "checkpoint:geopolitics",
    "completed"
  ].includes(sim.pipelineStatus.status);

  const hasActiveScenario = sim.activeScenario !== null;

  const tabs: { key: Tab; label: string; show: boolean }[] = [
    { key: "create", label: "새 시나리오", show: true },
    { key: "progress", label: "진행 상태", show: true },
    { key: "what_if", label: "What-If", show: hasActiveScenario },
    { key: "decisions", label: "결정", show: hasActiveScenario },
    { key: "list", label: "목록", show: true },
    { key: "graph", label: "그래프", show: showGraphTab },
    { key: "geopolitics", label: "지정학", show: isCompleted },
    { key: "timeline", label: "타임라인", show: isCompleted },
    { key: "report", label: "리포트", show: isCompleted },
    { key: "export", label: "내보내기", show: isCompleted },
    { key: "causal", label: "인과", show: hasActiveScenario },
    { key: "conversation", label: "대화", show: hasActiveScenario },
    { key: "compare", label: "비교", show: true },
    { key: "dashboard", label: "대시보드", show: true },
    { key: "health", label: "헬스", show: true },
  ];

  const tabMap = new Map(tabs.map(t => [t.key, t]));
  const activeGroup = getGroupForTab(tab);
  const activeGroupDef = TAB_GROUPS.find(g => g.key === activeGroup)!;
  const visibleSubTabs = activeGroupDef.tabs.filter(key => tabMap.get(key)?.show);

  const handleGroupClick = (groupKey: TabGroup) => {
    if (groupKey === activeGroup) return;
    const group = TAB_GROUPS.find(g => g.key === groupKey)!;
    const firstVisible = group.tabs.find(key => tabMap.get(key)?.show);
    if (firstVisible) setTab(firstVisible);
  };

  return (
    <div
      style={{
        position: "fixed",
        top: 0,
        right: 0,
        width: 400,
        height: "100dvh",
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
          aria-label="패널 닫기"
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
          <X size={18} aria-hidden="true" />
        </button>
      </div>

      {/* Tab groups */}
      <div
        style={{
          display: "flex",
          gap: 4,
          padding: "8px 12px",
          borderBottom: "1px solid var(--border-secondary)",
          flexShrink: 0,
          background: "var(--bg-primary)",
        }}
      >
        {TAB_GROUPS.map((g) => {
          const hasVisible = g.tabs.some(key => tabMap.get(key)?.show);
          const isActive = g.key === activeGroup;
          return (
            <button
              key={g.key}
              onClick={() => handleGroupClick(g.key)}
              disabled={!hasVisible}
              style={{
                flex: 1,
                padding: "6px 0",
                background: isActive ? "rgba(34, 211, 238, 0.12)" : "transparent",
                border: isActive ? "1px solid var(--accent-cyan)" : "1px solid var(--border-secondary)",
                borderRadius: 6,
                color: isActive ? "var(--accent-cyan)" : hasVisible ? "var(--text-muted)" : "var(--border-secondary)",
                fontSize: 11,
                fontWeight: isActive ? 700 : 500,
                cursor: hasVisible ? "pointer" : "default",
                transition: "all 0.15s ease",
                opacity: hasVisible ? 1 : 0.4,
              }}
            >
              {g.label}
            </button>
          );
        })}
      </div>

      {/* Sub-tabs */}
      <div
        style={{
          display: "flex",
          overflowX: "auto",
          scrollbarWidth: "none",
          borderBottom: "1px solid var(--border-secondary)",
          flexShrink: 0,
          minHeight: 36,
        }}
      >
        {visibleSubTabs.map((key) => {
          const t = tabMap.get(key)!;
          const isActive = tab === key;
          return (
            <button
              key={key}
              onClick={() => setTab(key)}
              style={{
                padding: "8px 14px",
                background: "transparent",
                border: "none",
                borderBottom: `2px solid ${isActive ? "var(--accent-cyan)" : "transparent"}`,
                color: isActive ? "var(--accent-cyan)" : "var(--text-muted)",
                fontSize: 12,
                fontWeight: isActive ? 600 : 400,
                cursor: "pointer",
                whiteSpace: "nowrap",
                transition: "color 0.15s, border-color 0.15s",
                flexShrink: 0,
              }}
            >
              {t.label}
            </button>
          );
        })}
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
            flexDirection: "column",
            gap: 6,
            flexShrink: 0,
          }}
        >
          <div role="alert" style={{ display: "flex", alignItems: "flex-start", gap: 8 }}>
            <AlertTriangle size={14} color="var(--accent-red)" style={{ marginTop: 1, flexShrink: 0 }} aria-hidden="true" />
            <div style={{ fontSize: 12, color: "var(--accent-red)", lineHeight: 1.4, flex: 1 }}>
              {sim.error}
            </div>
            <button
              onClick={sim.clearError}
              aria-label="오류 닫기"
              style={{
                background: "transparent",
                border: "none",
                color: "var(--accent-red)",
                cursor: "pointer",
                padding: 0,
                flexShrink: 0,
              }}
            >
              <X size={12} aria-hidden="true" />
            </button>
          </div>
          {sim.pipelineStatus?.status === "failed" && sim.activeScenario && (
            <button
              onClick={async () => {
                sim.clearError();
                try {
                  await retrySimulation(sim.activeScenario!.id);
                  setTab("progress");
                  sim.selectScenario(sim.activeScenario!);
                } catch { }
              }}
              style={{
                padding: "6px 10px",
                background: "rgba(239, 68, 68, 0.15)",
                border: "1px solid rgba(239, 68, 68, 0.3)",
                borderRadius: 4,
                color: "var(--accent-red)",
                fontSize: 11,
                fontWeight: 600,
                cursor: "pointer",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                gap: 4,
              }}
            >
              <RotateCcw size={11} aria-hidden="true" />
              마지막 체크포인트에서 재시도
            </button>
          )}
        </div>
      )}

      {/* Content */}
      <div
        style={{
          flex: 1,
          minHeight: 0,
          overflow: "auto",
          padding: 16,
          WebkitOverflowScrolling: "touch",
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
          hasCheckpoint && sim.checkpointData?.step === "decision" ? (
            <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
              <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                <span style={{ fontSize: 13, fontWeight: 700, color: "var(--text-primary)" }}>
                  AI 결정 지점
                </span>
                <span style={{
                  fontSize: 10, padding: "2px 6px", borderRadius: 999,
                  background: "rgba(245, 158, 11, 0.15)", color: "var(--accent-amber, #f59e0b)", fontWeight: 600,
                }}>
                  선택 대기
                </span>
              </div>
              <DecisionPointView
                scenarioId={sim.activeScenario!.id}
                type="seed_selection"
                onResolved={() => {}}
              />
              <DecisionPointView
                scenarioId={sim.activeScenario!.id}
                type="parameter_recommendation"
                onResolved={() => {}}
              />
              <button
                onClick={() => sim.continueCheckpoint()}
                style={{
                  width: "100%", padding: "10px 12px",
                  background: "var(--accent-cyan)", border: "none", borderRadius: 4,
                  color: "var(--bg-primary)", fontSize: 12, fontWeight: 700, cursor: "pointer",
                  display: "flex", alignItems: "center", justifyContent: "center", gap: 6,
                }}
              >
                선택 완료 — 시뮬레이션 시작
              </button>
            </div>
          ) : hasCheckpoint ? (
            <CheckpointReview
              checkpointData={sim.checkpointData!}
              onContinue={sim.continueCheckpoint}
              onCancel={() => setTab("list")}
            />
          ) : sim.pipelineStatus?.status?.startsWith("simulating:") ? (
            <div style={{ display: "flex", flexDirection: "column", height: "100%" }}>
              <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
                <div style={{ flex: 1 }}>
                  <PipelineProgress pipelineStatus={sim.pipelineStatus} onReview={() => {}} />
                </div>
              </div>
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

        {tab === "what_if" && (
          <WhatIfBranchView
            scenarioId={sim.activeScenario?.id}
            onOpenCompare={(branchId) => onOpenWhatIfCompare?.(branchId)}
          />
        )}

        {tab === "decisions" && sim.activeScenario && (
          <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
            <DecisionPointView
              scenarioId={sim.activeScenario.id}
              type="seed_selection"
              onResolved={() => {}}
            />
            <DecisionPointView
              scenarioId={sim.activeScenario.id}
              type="parameter_recommendation"
              onResolved={() => {}}
            />
          </div>
        )}

        {tab === "list" && (
          <>
            <ScenarioSearch
              onResults={(scenarios) => {
                sim.setFilteredScenarios?.(scenarios);
              }}
            />
            <ScenarioList
              scenarios={sim.filteredScenarios ?? sim.scenarios}
              activeId={sim.activeScenario?.id ?? null}
              onSelect={(s) => {
                sim.selectScenario(s);
                setTab("progress");
              }}
              onDelete={sim.deleteScenario}
            />
          </>
        )}

        {tab === "timeline" && (
          <SimulationTimeline actions={sim.simulationResults} />
        )}

        {tab === "graph" && sim.activeScenario && (
          <GraphTab scenarioId={sim.activeScenario.id} />
        )}

        {tab === "geopolitics" && sim.activeScenario && (
          <GeopoliticsView scenarioId={sim.activeScenario.id} onFlyTo={onFlyTo} />
        )}

        {tab === "report" && (
          <ReportViewer markdown={sim.reportMarkdown} />
        )}

        {tab === "export" && (
          <ExportPanel scenarioId={sim.activeScenario?.id} />
        )}

        {tab === "conversation" && (
          <ConversationPanel scenarioId={sim.activeScenario?.id} />
        )}

        {tab === "causal" && (
          <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
            <CausalDAGView />
            {sim.activeScenario && (
              <CausalQueryPanel scenarioId={sim.activeScenario.id} />
            )}
          </div>
        )}

        {tab === "compare" && (
          <ComparisonView scenarios={sim.scenarios} />
        )}

        {tab === "dashboard" && <AnalystDashboard />}

        {tab === "health" && <HealthDashboard />}
      </div>
    </div>
  );
}
