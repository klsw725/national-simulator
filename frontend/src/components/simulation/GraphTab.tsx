"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { X } from "lucide-react";
import type { GraphData, GraphNode, NodeDetail, GraphFilters } from "@/types/simulation";
import { getLiveGraphData } from "@/lib/gatewayApi";
import GraphViewer from "./GraphViewer";

const COLOR_MAP: Record<string, string> = {
  person: "#22d3ee",
  organization: "#f59e0b",
  location: "#a78bfa",
  event: "#f472b6",
  default: "#60a5fa",
};

interface Props {
  scenarioId: string;
}

export default function GraphTab({ scenarioId }: Props) {
  const [graphData, setGraphData] = useState<GraphData | null>(null);
  const [selectedNode, setSelectedNode] = useState<NodeDetail | null>(null);
  const [filters, setFilters] = useState<GraphFilters>({ entityTypes: [], relationTypes: [] });
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    getLiveGraphData(scenarioId)
      .then((data) => {
        if (!cancelled) {
          setGraphData(data);
          setLoading(false);
        }
      })
      .catch(() => {
        if (!cancelled) setLoading(false);
      });
    return () => { cancelled = true; };
  }, [scenarioId]);

  const availableEntityTypes = useMemo(() => {
    if (!graphData?.nodes?.length) return [];
    const types = new Set<string>();
    graphData.nodes.forEach((n) => {
      const t = n.entityType?.toLowerCase() ?? n.labels[0]?.toLowerCase();
      if (t) types.add(t);
    });
    return Array.from(types).sort();
  }, [graphData]);

  const availableRelationTypes = useMemo(() => {
    if (!graphData?.edges?.length) return [];
    const types = new Set<string>();
    graphData.edges.forEach((e) => {
      if (e.name) types.add(e.name);
    });
    return Array.from(types).sort();
  }, [graphData]);

  const filteredGraphData = useMemo((): GraphData | null => {
    if (!graphData) return null;
    const hasEntityFilter = filters.entityTypes.length > 0;
    const hasRelationFilter = filters.relationTypes.length > 0;
    if (!hasEntityFilter && !hasRelationFilter) return graphData;

    const filteredNodes = hasEntityFilter
      ? graphData.nodes.filter((n) => {
          const t = n.entityType?.toLowerCase() ?? n.labels[0]?.toLowerCase() ?? "";
          return filters.entityTypes.includes(t);
        })
      : graphData.nodes;

    const nodeIds = new Set(filteredNodes.map((n) => n.uuid));

    let filteredEdges = graphData.edges.filter(
      (e) => nodeIds.has(e.source_node_uuid) && nodeIds.has(e.target_node_uuid)
    );

    if (hasRelationFilter) {
      filteredEdges = filteredEdges.filter((e) => filters.relationTypes.includes(e.name));
    }

    return {
      nodes: filteredNodes,
      edges: filteredEdges,
      node_count: filteredNodes.length,
      edge_count: filteredEdges.length,
    };
  }, [graphData, filters]);

  const handleNodeClick = useCallback(
    (nodeId: string, node: GraphNode) => {
      if (!graphData) return;
      if (selectedNode?.id === nodeId) {
        setSelectedNode(null);
        return;
      }
      const relationships: NodeDetail["relationships"] = [];
      graphData.edges.forEach((e) => {
        if (e.source_node_uuid === nodeId) {
          const target = graphData.nodes.find((n) => n.uuid === e.target_node_uuid);
          if (target) relationships.push({ targetName: target.name, type: e.name, direction: "outgoing" });
        }
        if (e.target_node_uuid === nodeId) {
          const source = graphData.nodes.find((n) => n.uuid === e.source_node_uuid);
          if (source) relationships.push({ targetName: source.name, type: e.name, direction: "incoming" });
        }
      });
      setSelectedNode({
        id: nodeId,
        name: node.name,
        type: node.entityType?.toLowerCase() ?? node.labels[0]?.toLowerCase() ?? "unknown",
        labels: node.labels,
        attributes: node.attributes,
        relationships,
      });
    },
    [graphData, selectedNode?.id]
  );

  const toggleEntityType = useCallback((type: string) => {
    setFilters((prev) => {
      const next = prev.entityTypes.includes(type)
        ? prev.entityTypes.filter((t) => t !== type)
        : [...prev.entityTypes, type];
      return { ...prev, entityTypes: next };
    });
  }, []);

  const toggleRelationType = useCallback((type: string) => {
    setFilters((prev) => {
      const next = prev.relationTypes.includes(type)
        ? prev.relationTypes.filter((t) => t !== type)
        : [...prev.relationTypes, type];
      return { ...prev, relationTypes: next };
    });
  }, []);

  if (loading) {
    return (
      <div style={{ height: 200, display: "flex", alignItems: "center", justifyContent: "center", color: "var(--text-muted)", fontSize: 12 }}>
        그래프 데이터 로딩 중...
      </div>
    );
  }

  if (!graphData?.nodes?.length) {
    return (
      <div style={{ height: 200, display: "flex", alignItems: "center", justifyContent: "center", color: "var(--text-muted)", fontSize: 12 }}>
        그래프 데이터가 없습니다
      </div>
    );
  }

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
      {/* Entity type filter pills */}
      {availableEntityTypes.length > 0 && (
        <div style={{ display: "flex", flexWrap: "wrap", gap: 6 }}>
          {availableEntityTypes.map((type) => {
            const active = filters.entityTypes.length === 0 || filters.entityTypes.includes(type);
            const color = COLOR_MAP[type] ?? COLOR_MAP.default;
            return (
              <button
                key={type}
                onClick={() => toggleEntityType(type)}
                style={{
                  padding: "3px 10px",
                  fontSize: 11,
                  borderRadius: 12,
                  border: `1px solid ${color}`,
                  background: active ? color + "22" : "transparent",
                  color: active ? color : "var(--text-muted)",
                  cursor: "pointer",
                  opacity: active ? 1 : 0.5,
                  transition: "all 0.15s",
                }}
              >
                {type}
              </button>
            );
          })}
        </div>
      )}

      {/* Relation type filter pills */}
      {availableRelationTypes.length > 0 && (
        <div style={{ display: "flex", flexWrap: "wrap", gap: 6 }}>
          {availableRelationTypes.map((type) => {
            const active = filters.relationTypes.length === 0 || filters.relationTypes.includes(type);
            return (
              <button
                key={type}
                onClick={() => toggleRelationType(type)}
                style={{
                  padding: "3px 10px",
                  fontSize: 11,
                  borderRadius: 12,
                  border: "1px solid var(--border-secondary)",
                  background: active ? "var(--bg-primary)" : "transparent",
                  color: active ? "var(--text-primary)" : "var(--text-muted)",
                  cursor: "pointer",
                  opacity: active ? 1 : 0.5,
                  transition: "all 0.15s",
                }}
              >
                {type}
              </button>
            );
          })}
        </div>
      )}

      {/* GraphViewer standalone */}
      <GraphViewer
        graphData={filteredGraphData}
        taskStatus={null}
        standalone
        selectedNodeId={selectedNode?.id ?? null}
        onNodeClick={handleNodeClick}
      />

      {/* Node detail panel */}
      {selectedNode && (
        <div
          style={{
            borderTop: "1px solid var(--border-secondary)",
            padding: "10px 0 0",
            maxHeight: 200,
            overflowY: "auto",
          }}
        >
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 8 }}>
            <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
              <span style={{ fontSize: 14, fontWeight: 600, color: "var(--text-primary)" }}>
                {selectedNode.name}
              </span>
              <span
                style={{
                  fontSize: 10,
                  padding: "2px 8px",
                  borderRadius: 10,
                  background: (COLOR_MAP[selectedNode.type] ?? COLOR_MAP.default) + "22",
                  color: COLOR_MAP[selectedNode.type] ?? COLOR_MAP.default,
                  fontWeight: 500,
                }}
              >
                {selectedNode.type}
              </span>
            </div>
            <button
              onClick={() => setSelectedNode(null)}
              style={{
                background: "transparent",
                border: "none",
                cursor: "pointer",
                color: "var(--text-muted)",
                padding: 2,
                display: "flex",
                alignItems: "center",
              }}
            >
              <X size={14} />
            </button>
          </div>

          {selectedNode.relationships.length > 0 ? (
            <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
              {selectedNode.relationships.map((rel, i) => (
                <div
                  key={i}
                  style={{
                    fontSize: 11,
                    color: "var(--text-muted)",
                    display: "flex",
                    alignItems: "center",
                    gap: 4,
                  }}
                >
                  <span style={{ color: "var(--text-primary)", fontWeight: 500 }}>
                    {rel.direction === "outgoing" ? "\u2192" : "\u2190"}
                  </span>
                  <span style={{ color: "var(--accent-cyan)" }}>{rel.type}</span>
                  <span style={{ color: "var(--text-primary)" }}>{rel.targetName}</span>
                </div>
              ))}
            </div>
          ) : (
            <div style={{ fontSize: 11, color: "var(--text-muted)" }}>
              연결된 관계가 없습니다
            </div>
          )}
        </div>
      )}
    </div>
  );
}
