"use client";

import { useEffect, useRef, useState, useCallback } from "react";
import * as d3 from "d3";
import { getCausalDomainDAG, type CausalDAGResponse } from "@/lib/gatewayApi";
import { Loader2, AlertCircle } from "lucide-react";

interface NodeDatum extends d3.SimulationNodeDatum {
  id: string;
  node_type?: string;
}

interface LinkDatum extends d3.SimulationLinkDatum<NodeDatum> {
  edge_type?: string;
  strength?: number;
}

const NODE_COLORS: Record<string, string> = {
  state: "#3b82f6",
  event: "#f97316",
  decision: "#ef4444",
  outcome: "#8b5cf6",
};
const DEFAULT_NODE_COLOR = "#6b7280";

export default function CausalDAGView() {
  const svgRef = useRef<SVGSVGElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const [data, setData] = useState<CausalDAGResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selected, setSelected] = useState<NodeDatum | null>(null);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const res = await getCausalDomainDAG();
        if (!cancelled) setData(res);
      } catch {
        if (!cancelled) setError("DAG 데이터를 불러올 수 없습니다");
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => { cancelled = true; };
  }, []);

  const renderGraph = useCallback(() => {
    if (!data || !svgRef.current || !containerRef.current) return;

    const svg = d3.select(svgRef.current);
    svg.selectAll("*").remove();

    const { width } = containerRef.current.getBoundingClientRect();
    const height = 420;

    svg.attr("width", width).attr("height", height);

    const nodes: NodeDatum[] = data.dag.nodes.map((n) => ({ ...n }));
    const links: LinkDatum[] = data.dag.links.map((l) => ({
      source: l.source,
      target: l.target,
      edge_type: l.edge_type,
      strength: l.strength,
    }));

    const g = svg.append("g");

    const zoom = d3.zoom<SVGSVGElement, unknown>()
      .scaleExtent([0.3, 3])
      .on("zoom", (event) => g.attr("transform", event.transform));
    svg.call(zoom);

    svg.append("defs").append("marker")
      .attr("id", "dag-arrow")
      .attr("viewBox", "0 -4 8 8")
      .attr("refX", 20)
      .attr("refY", 0)
      .attr("markerWidth", 6)
      .attr("markerHeight", 6)
      .attr("orient", "auto")
      .append("path")
      .attr("d", "M0,-4L8,0L0,4")
      .attr("fill", "#4b5563");

    const simulation = d3.forceSimulation<NodeDatum>(nodes)
      .force("link", d3.forceLink<NodeDatum, LinkDatum>(links).id((d) => d.id).distance(100))
      .force("charge", d3.forceManyBody().strength(-300))
      .force("center", d3.forceCenter(width / 2, height / 2))
      .force("collision", d3.forceCollide(30));

    const link = g.append("g")
      .selectAll<SVGLineElement, LinkDatum>("line")
      .data(links)
      .join("line")
      .attr("stroke", "#4b5563")
      .attr("stroke-width", (d) => Math.max(1, (d.strength ?? 0.5) * 3))
      .attr("stroke-opacity", 0.6)
      .attr("marker-end", "url(#dag-arrow)");

    const node = g.append("g")
      .selectAll<SVGGElement, NodeDatum>("g")
      .data(nodes)
      .join("g")
      .style("cursor", "pointer")
      .on("click", (_, d) => setSelected(d))
      .call(
        d3.drag<SVGGElement, NodeDatum>()
          .on("start", (event, d) => {
            if (!event.active) simulation.alphaTarget(0.3).restart();
            d.fx = d.x;
            d.fy = d.y;
          })
          .on("drag", (event, d) => {
            d.fx = event.x;
            d.fy = event.y;
          })
          .on("end", (event, d) => {
            if (!event.active) simulation.alphaTarget(0);
            d.fx = null;
            d.fy = null;
          }),
      );

    node.append("circle")
      .attr("r", 12)
      .attr("fill", (d) => NODE_COLORS[d.node_type ?? ""] ?? DEFAULT_NODE_COLOR)
      .attr("stroke", "rgba(255,255,255,0.15)")
      .attr("stroke-width", 1.5);

    node.append("text")
      .text((d) => d.id)
      .attr("dy", -18)
      .attr("text-anchor", "middle")
      .style("font-size", "10px")
      .style("fill", "#d1d5db")
      .style("pointer-events", "none");

    simulation.on("tick", () => {
      link
        .attr("x1", (d) => (d.source as NodeDatum).x!)
        .attr("y1", (d) => (d.source as NodeDatum).y!)
        .attr("x2", (d) => (d.target as NodeDatum).x!)
        .attr("y2", (d) => (d.target as NodeDatum).y!);
      node.attr("transform", (d) => `translate(${d.x},${d.y})`);
    });

    return () => { simulation.stop(); };
  }, [data]);

  useEffect(() => {
    const cleanup = renderGraph();
    return () => { cleanup?.(); };
  }, [renderGraph]);

  useEffect(() => {
    if (!containerRef.current || !data) return;
    const observer = new ResizeObserver(() => renderGraph());
    observer.observe(containerRef.current);
    return () => observer.disconnect();
  }, [data, renderGraph]);

  if (loading) {
    return (
      <div
        style={{
          height: 420,
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          gap: 8,
          color: "var(--text-muted)",
          fontSize: 13,
          background: "var(--bg-tertiary)",
          borderRadius: 8,
          border: "1px solid var(--border-secondary)",
        }}
      >
        <Loader2 size={16} style={{ animation: "spin 1s linear infinite" }} />
        DAG 로딩 중...
      </div>
    );
  }

  if (error) {
    return (
      <div
        style={{
          height: 200,
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          gap: 8,
          color: "#ef4444",
          fontSize: 13,
          background: "var(--bg-tertiary)",
          borderRadius: 8,
          border: "1px solid var(--border-secondary)",
        }}
      >
        <AlertCircle size={16} />
        {error}
      </div>
    );
  }

  const connectedEdges = selected
    ? data!.dag.links.filter(
        (l) => l.source === selected.id || l.target === selected.id,
      )
    : [];

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
        Causal DAG
      </div>
      <div
        ref={containerRef}
        style={{
          background: "var(--bg-tertiary)",
          border: "1px solid var(--border-secondary)",
          borderRadius: 8,
          overflow: "hidden",
          position: "relative",
        }}
      >
        <svg ref={svgRef} style={{ display: "block" }} />

        <div
          style={{
            position: "absolute",
            bottom: 8,
            left: 8,
            display: "flex",
            gap: 10,
            fontSize: 9,
            color: "var(--text-muted)",
          }}
        >
          {Object.entries(NODE_COLORS).map(([type, color]) => (
            <span key={type} style={{ display: "flex", alignItems: "center", gap: 3 }}>
              <span
                style={{
                  width: 8,
                  height: 8,
                  borderRadius: "50%",
                  background: color,
                  display: "inline-block",
                }}
              />
              {type}
            </span>
          ))}
        </div>

        {selected && (
          <div
            style={{
              position: "absolute",
              top: 8,
              right: 8,
              background: "var(--bg-secondary)",
              border: "1px solid var(--border-secondary)",
              borderRadius: 6,
              padding: "8px 12px",
              fontSize: 11,
              color: "var(--text-primary)",
              maxWidth: 200,
            }}
          >
            <div style={{ fontWeight: 700, marginBottom: 4 }}>{selected.id}</div>
            <div style={{ fontSize: 10, color: "var(--text-muted)", marginBottom: 6 }}>
              타입: {selected.node_type ?? "unknown"}
            </div>
            {connectedEdges.length > 0 && (
              <div style={{ fontSize: 10, color: "var(--text-muted)" }}>
                연결: {connectedEdges.length}개 엣지
              </div>
            )}
            <button
              onClick={() => setSelected(null)}
              style={{
                marginTop: 6,
                background: "transparent",
                border: "none",
                color: "var(--text-muted)",
                fontSize: 10,
                cursor: "pointer",
                padding: 0,
                textDecoration: "underline",
              }}
            >
              닫기
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
