"use client";

import { memo, useEffect, useMemo, useRef } from "react";
import * as d3 from "d3";
import type { GraphData, GraphTaskStatus } from "@/types/simulation";

interface Props {
  graphData: GraphData | null;
  taskStatus: GraphTaskStatus | null;
  standalone?: boolean;
  selectedNodeId?: string | null;
  onNodeClick?: (nodeId: string, node: import("@/types/simulation").GraphNode) => void;
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

import { ENTITY_COLOR_MAP as COLOR_MAP } from "@/lib/chartColors";

function GraphViewer({ graphData, taskStatus, standalone, selectedNodeId, onNodeClick }: Props) {
  const svgRef = useRef<SVGSVGElement | null>(null);
  const simRef = useRef<d3.Simulation<SimNode, SimLink> | null>(null);

  const progress = Math.max(0, Math.min(100, Math.round(taskStatus?.progress ?? 0)));
  const nodeCount = graphData?.node_count ?? 0;
  const edgeCount = graphData?.edge_count ?? 0;

  const graphReady = useMemo(
    () => Boolean(graphData?.nodes?.length && graphData?.edges?.length),
    [graphData]
  );

  // Selection highlight effect (runs without re-creating simulation)
  useEffect(() => {
    if (!svgRef.current || !graphReady) return;
    const svg = d3.select(svgRef.current);

    const connectedIds = new Set<string>();
    if (selectedNodeId && graphData) {
      graphData.edges.forEach((e) => {
        if (e.source_node_uuid === selectedNodeId) connectedIds.add(e.target_node_uuid);
        if (e.target_node_uuid === selectedNodeId) connectedIds.add(e.source_node_uuid);
      });
    }

    svg.selectAll<SVGCircleElement, SimNode>("circle").each(function (d) {
      const el = d3.select(this);
      const key = d.entityType?.toLowerCase() ?? d.labels[0]?.toLowerCase() ?? "default";
      const baseColor = COLOR_MAP[key] ?? COLOR_MAP.default;

      if (!selectedNodeId) {
        el.attr("r", standalone ? 7 : 5)
          .attr("opacity", 1)
          .attr("filter", null);
      } else if (d.id === selectedNodeId) {
        el.attr("r", 12).attr("opacity", 1).attr("filter", `drop-shadow(0 0 6px ${baseColor})`);
      } else if (connectedIds.has(d.id)) {
        el.attr("r", standalone ? 7 : 5).attr("opacity", 0.9).attr("filter", null);
      } else {
        el.attr("r", standalone ? 7 : 5).attr("opacity", 0.3).attr("filter", null);
      }
    });

    svg.selectAll<SVGLineElement, SimLink>("line").each(function (d) {
      const el = d3.select(this);
      const srcId = typeof d.source === "string" ? d.source : (d.source as SimNode).id;
      const tgtId = typeof d.target === "string" ? d.target : (d.target as SimNode).id;
      if (!selectedNodeId) {
        el.attr("stroke-width", 1).attr("stroke-opacity", 0.8).attr("stroke", "var(--border-secondary)");
      } else if (srcId === selectedNodeId || tgtId === selectedNodeId) {
        el.attr("stroke-width", 2.5).attr("stroke-opacity", 1).attr("stroke", "var(--accent-cyan)");
      } else {
        el.attr("stroke-width", 1).attr("stroke-opacity", 0.15).attr("stroke", "var(--border-secondary)");
      }
    });

    // Dim edge labels of non-connected edges
    svg.selectAll<SVGTextElement, SimLink>("g:nth-child(2) text").each(function (d) {
      const el = d3.select(this);
      const srcId = typeof d.source === "string" ? d.source : (d.source as SimNode).id;
      const tgtId = typeof d.target === "string" ? d.target : (d.target as SimNode).id;
      if (!selectedNodeId) {
        el.attr("opacity", 1);
      } else if (srcId === selectedNodeId || tgtId === selectedNodeId) {
        el.attr("opacity", 1);
      } else {
        el.attr("opacity", 0.15);
      }
    });
  }, [selectedNodeId, graphReady, graphData, standalone]);

  useEffect(() => {
    if (!svgRef.current || !graphData?.nodes?.length) return;

    simRef.current?.stop();

    const width = standalone ? 380 : 360;
    const height = standalone ? 320 : 240;
    const nodeRadius = standalone ? 7 : 5;

    const svg = d3.select(svgRef.current);
    svg.selectAll("*").remove();

    // Add zoom for standalone mode
    const container = svg.append("g");
    if (standalone) {
      const zoomBehavior = d3.zoom<SVGSVGElement, unknown>()
        .scaleExtent([0.3, 4])
        .on("zoom", (event) => {
          container.attr("transform", event.transform);
        });
      svg.call(zoomBehavior);
    }
    const root = standalone ? container : svg;

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
      .force("link", d3.forceLink<SimNode, SimLink>(links).id((d) => d.id).distance(standalone ? 60 : 48))
      .force("charge", d3.forceManyBody().strength(standalone ? -180 : -140))
      .force("center", d3.forceCenter(width / 2, height / 2))
      .force("collision", d3.forceCollide(standalone ? 16 : 12));

    simRef.current = simulation;

    const linksG = root
      .append("g")
      .attr("stroke", "var(--border-secondary)")
      .attr("stroke-opacity", 0.8)
      .selectAll("line")
      .data(links)
      .join("line")
      .attr("stroke-width", 1);

    const edgeLabels = root
      .append("g")
      .selectAll("text")
      .data(links)
      .join("text")
      .attr("font-size", 8)
      .attr("fill", "var(--text-muted)")
      .attr("text-anchor", "middle")
      .text((d) => d.name);

    const nodesG = root
      .append("g")
      .selectAll("circle")
      .data(nodes)
      .join("circle")
      .attr("r", nodeRadius)
      .attr("fill", (d) => {
        const key = d.entityType?.toLowerCase() ?? d.labels[0]?.toLowerCase() ?? "default";
        return COLOR_MAP[key] ?? COLOR_MAP.default;
      })
      .attr("stroke", "#0b1220")
      .attr("stroke-width", 1)
      .style("cursor", onNodeClick ? "pointer" : "default");

    if (onNodeClick) {
      nodesG.on("click", (_event, d) => {
        const graphNode = graphData.nodes.find((n) => n.uuid === d.id);
        if (graphNode) onNodeClick(d.id, graphNode);
      });
    }

    const nodeLabels = root
      .append("g")
      .selectAll("text")
      .data(nodes)
      .join("text")
      .attr("font-size", 9)
      .attr("fill", "var(--text-primary)")
      .text((d) => standalone ? d.name : d.name.slice(0, 16));

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
  }, [graphData, standalone, onNodeClick]);

  const viewBox = standalone ? "0 0 380 320" : "0 0 360 240";

  return (
    <div style={{ border: standalone ? "none" : "1px solid var(--border-secondary)", borderRadius: 6, padding: standalone ? 0 : 10 }}>
      <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 8 }}>
        <span style={{ fontSize: 12, color: "var(--text-primary)", fontWeight: 600 }}>지식 그래프</span>
        <span style={{ fontSize: 11, color: "var(--text-muted)" }}>노드 {nodeCount} / 엣지 {edgeCount}</span>
      </div>

      {!standalone && taskStatus?.status === "processing" && (
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
        <svg ref={svgRef} width="100%" viewBox={viewBox} style={{ display: "block", background: "var(--bg-secondary)", borderRadius: 4 }} />
      ) : (
        <div style={{ height: standalone ? 240 : 180, display: "flex", alignItems: "center", justifyContent: "center", color: "var(--text-muted)", fontSize: 12, textAlign: "center", padding: 16, lineHeight: 1.5 }}>
          그래프 데이터 대기 중...<br />
          실시간 이벤트가 없으면 체크포인트 기준 그래프를 표시합니다.
        </div>
      )}
    </div>
  );
}

export default memo(GraphViewer);
