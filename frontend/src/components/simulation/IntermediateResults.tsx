"use client";

import { memo } from "react";
import GraphViewer from "./GraphViewer";
import LiveActionFeed from "./LiveActionFeed";
import LiveStats from "./LiveStats";
import { useLiveSimulation } from "@/hooks/useLiveSimulation";

interface Props {
  pipelineStatus: string;
  scenarioId: string | null;
}

function StatusView({ text }: { text: string }) {
  return (
    <div
      style={{
        height: "100%",
        border: "1px solid var(--border-secondary)",
        borderRadius: 6,
        background: "var(--bg-secondary)",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        color: "var(--text-primary)",
        fontSize: 13,
        gap: 8,
      }}
    >
      <span>⏳</span>
      <span>{text}</span>
    </div>
  );
}

function IntermediateResults({ pipelineStatus, scenarioId }: Props) {
  const { stats, actions, graphTaskStatus, graphData, profiles, config, isLive } = useLiveSimulation(
    scenarioId,
    pipelineStatus
  );

  if (!isLive) {
    return null;
  }

  if (pipelineStatus === "simulating:ontology") {
    return <StatusView text="온톨로지 생성 중..." />;
  }

  if (pipelineStatus === "simulating:create") {
    return <StatusView text="시뮬레이션 생성 중..." />;
  }

  if (pipelineStatus === "simulating:report") {
    return <StatusView text="보고서 생성 중..." />;
  }

  if (pipelineStatus === "simulating:graph_build") {
    return (
      <div style={{ height: "100%", display: "flex", flexDirection: "column", gap: 10 }}>
        {graphTaskStatus && (
          <div style={{ fontSize: 11, color: "var(--text-muted)" }}>
            {graphTaskStatus.message ?? "그래프 빌드 진행 중"}
          </div>
        )}
        <GraphViewer graphData={graphData} taskStatus={graphTaskStatus} />
      </div>
    );
  }

  if (pipelineStatus === "simulating:prepare") {
    return (
      <div style={{ height: "100%", display: "flex", flexDirection: "column", gap: 10 }}>
        <div
          style={{
            border: "1px solid var(--border-secondary)",
            borderRadius: 6,
            padding: 10,
            background: "var(--bg-secondary)",
            color: "var(--text-primary)",
            fontSize: 12,
          }}
        >
          프로필 생성 중: {profiles?.count ?? 0}/{profiles?.total_expected ?? 0}
        </div>

        <div
          style={{
            border: "1px solid var(--border-secondary)",
            borderRadius: 6,
            padding: 10,
            background: "var(--bg-secondary)",
            color: "var(--text-muted)",
            fontSize: 12,
            lineHeight: 1.5,
          }}
        >
          {config?.summary
            ? `${config.summary.total_agents}개 에이전트, ${config.summary.simulation_hours}시간 시뮬레이션`
            : "설정 요약 생성 중..."}
        </div>
      </div>
    );
  }

  if (pipelineStatus === "simulating:running") {
    return (
      <div style={{ height: "100%", display: "flex", flexDirection: "column", gap: 10 }}>
        <LiveStats stats={stats} />
        <div style={{ flex: 1, minHeight: 0 }}>
          <LiveActionFeed actions={actions} />
        </div>
      </div>
    );
  }

  return null;
}

export default memo(IntermediateResults);
