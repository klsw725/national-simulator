"use client";

import { useEffect, useMemo, useRef } from "react";
import * as d3 from "d3";
import type { GraphData, GraphTaskStatus } from "@/types/simulation";

interface Props {
  graphData: GraphData | null;
  taskStatus: GraphTaskStatus | null;
}

type SimNode = d3.SimulationNodeDatum & {
  id: string;
  name: string;
  entityType?: string;
  labels: string[];
};

type SimLink = d3.SimulationLinkDatum<SimNode> & {
  source: string | SimNode;
  target: string | SimNode;
  name: string;
};

const COLOR_MAP: Record<string, string> = {
  person: "#22d3ee",
  organization: "#f59e0b",
  location: "#a78bfa",
  event: "#f472b6",
  default: "#60a5fa",
};

export default function GraphViewer({ graphData, taskStatus }: Props) {
  const svgRef = useRef<SVGSVGElement | null>(null);
  const simRef = useRef<d3.Simulation<SimNode, SimLink> | null>(null);

  const progress = Math.max(0, Math.min(100, Math.round(taskStatus?.progress ?? 0)));
  const nodeCount = graphData?.node_count ?? 0;
  const edgeCount = graphData?.edge_count ?? 0;

  const graphReady = useMemo(
    () => Boolean(graphData?.nodes?.length && graphData?.edges?.length),
    [graphData]
  );

  useEffect(() => {
    if (!svgRef.current || !graphData?.nodes?.length) return;

    simRef.current?.stop();

    const width = 360;
    const height = 240;

    const svg = d3.select(svgRef.current);
    svg.selectAll("*").remove();

    const nodes: SimNode[] = graphData.nodes.map((node) => ({
      id: node.uuid,
      name: node.name,
      entityType: node.entityType,
      labels: node.labels,
    }));

    const links: SimLink[] = graphData.edges.map((edge) => ({
      source: edge.source_node_uuid,
      target: edge.target_node_uuid,
      name: edge.name,
    }));

    const simulation = d3
      .forceSimulation<SimNode>(nodes)
      .force("link", d3.forceLink<SimNode, SimLink>(links).id((d) => d.id).distance(48))
      .force("charge", d3.forceManyBody().strength(-140))
      .force("center", d3.forceCenter(width / 2, height / 2))
      .force("collision", d3.forceCollide(12));

    simRef.current = simulation;

    const linksG = svg
      .append("g")
      .attr("stroke", "var(--border-secondary)")
      .attr("stroke-opacity", 0.8)
      .selectAll("line")
      .data(links)
      .join("line")
      .attr("stroke-width", 1);

    const edgeLabels = svg
      .append("g")
      .selectAll("text")
      .data(links)
      .join("text")
      .attr("font-size", 8)
      .attr("fill", "var(--text-muted)")
      .attr("text-anchor", "middle")
      .text((d) => d.name);

    const nodesG = svg
      .append("g")
      .selectAll("circle")
      .data(nodes)
      .join("circle")
      .attr("r", 5)
      .attr("fill", (d) => {
        const key = d.entityType?.toLowerCase() ?? d.labels[0]?.toLowerCase() ?? "default";
        return COLOR_MAP[key] ?? COLOR_MAP.default;
      })
      .attr("stroke", "#0b1220")
      .attr("stroke-width", 1);

    const nodeLabels = svg
      .append("g")
      .selectAll("text")
      .data(nodes)
      .join("text")
      .attr("font-size", 9)
      .attr("fill", "var(--text-primary)")
      .text((d) => d.name.slice(0, 16));

    simulation.on("tick", () => {
      linksG
        .attr("x1", (d) => (d.source as SimNode).x ?? 0)
        .attr("y1", (d) => (d.source as SimNode).y ?? 0)
        .attr("x2", (d) => (d.target as SimNode).x ?? 0)
        .attr("y2", (d) => (d.target as SimNode).y ?? 0);

      edgeLabels
        .attr("x", (d) => (((d.source as SimNode).x ?? 0) + ((d.target as SimNode).x ?? 0)) / 2)
        .attr("y", (d) => (((d.source as SimNode).y ?? 0) + ((d.target as SimNode).y ?? 0)) / 2 - 4);

      nodesG.attr("cx", (d) => d.x ?? 0).attr("cy", (d) => d.y ?? 0);

      nodeLabels.attr("x", (d) => (d.x ?? 0) + 7).attr("y", (d) => (d.y ?? 0) + 3);
    });

    return () => {
      simulation.stop();
    };
  }, [graphData]);

  return (
    <div style={{ border: "1px solid var(--border-secondary)", borderRadius: 6, padding: 10 }}>
      <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 8 }}>
        <span style={{ fontSize: 12, color: "var(--text-primary)", fontWeight: 600 }}>지식 그래프</span>
        <span style={{ fontSize: 11, color: "var(--text-muted)" }}>노드 {nodeCount} / 엣지 {edgeCount}</span>
      </div>

      {taskStatus?.status === "processing" && (
        <div style={{ marginBottom: 8 }}>
          <div style={{ fontSize: 11, color: "var(--text-muted)", marginBottom: 4 }}>
            그래프 빌드 중 {progress}%
          </div>
          <div style={{ height: 6, borderRadius: 999, background: "var(--border-secondary)", overflow: "hidden" }}>
            <div
              style={{
                width: `${progress}%`,
                height: "100%",
                background: "var(--accent-cyan)",
                transition: "width 0.3s ease",
              }}
            />
          </div>
        </div>
      )}

      {graphReady ? (
        <svg ref={svgRef} width="100%" viewBox="0 0 360 240" style={{ display: "block", background: "var(--bg-secondary)", borderRadius: 4 }} />
      ) : (
        <div style={{ height: 180, display: "flex", alignItems: "center", justifyContent: "center", color: "var(--text-muted)", fontSize: 12 }}>
          그래프 데이터 대기 중...
        </div>
      )}
    </div>
  );
}
