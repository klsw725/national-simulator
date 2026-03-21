"use client";

import { useEffect, useState } from "react";
import { Pause, Play, Eye, Edit3, Check, ChevronRight } from "lucide-react";
import type { CheckpointData } from "@/types/simulation";
import { getSeed } from "@/lib/gatewayApi";

const STEP_ORDER = ["seed", "ontology", "graph", "profiles", "config"] as const;

const STEP_LABELS: Record<string, string> = {
  seed: "Seed",
  ontology: "Ontology",
  graph: "Graph",
  profiles: "Profiles",
  config: "Config",
};

interface Props {
  checkpointData: CheckpointData;
  onContinue: (edits?: Record<string, unknown>) => void;
  onCancel: () => void;
}

export default function CheckpointReview({ checkpointData, onContinue, onCancel }: Props) {
  const { step, data, editable } = checkpointData;
  const currentIdx = STEP_ORDER.indexOf(step as typeof STEP_ORDER[number]);

  const [seedText, setSeedText] = useState<string>(
    (data?.seed_text as string) ?? ""
  );
  const [maxRounds, setMaxRounds] = useState<number>(
    (data?.max_rounds as number) ?? 10
  );
  const [seedMeta, setSeedMeta] = useState<{
    vessels_count: number;
    actors_identified: string[];
    resolved_entity_count: number;
    used_observation_ids: string[];
    web_search_count: number;
    tension_score: number;
  } | null>(null);

  useEffect(() => {
    if (step === "seed" && checkpointData.scenario_id) {
      getSeed(checkpointData.scenario_id)
        .then((res) => setSeedMeta(res.metadata))
        .catch(() => {});
    }
  }, [step, checkpointData.scenario_id]);

  const handleContinue = () => {
    if (step === "seed" && editable) {
      onContinue({ seed_text: seedText });
    } else if (step === "config" && editable) {
      onContinue({ max_rounds: maxRounds });
    } else {
      onContinue();
    }
  };

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: 4,
          padding: "10px 12px",
          background: "var(--bg-primary)",
          borderRadius: 6,
          border: "1px solid var(--border-secondary)",
        }}
      >
        {STEP_ORDER.map((s, i) => {
          const isCurrent = i === currentIdx;
          const isDone = i < currentIdx;
          return (
            <div key={s} style={{ display: "flex", alignItems: "center", gap: 4 }}>
              <div
                style={{
                  width: 22,
                  height: 22,
                  borderRadius: "50%",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  fontSize: 10,
                  fontWeight: 700,
                  border: isCurrent
                    ? "2px solid var(--accent-amber, #f59e0b)"
                    : isDone
                      ? "2px solid var(--status-connected)"
                      : "1px solid var(--border-secondary)",
                  background: isCurrent
                    ? "rgba(245, 158, 11, 0.15)"
                    : isDone
                      ? "rgba(34, 197, 94, 0.1)"
                      : "transparent",
                  color: isCurrent
                    ? "var(--accent-amber, #f59e0b)"
                    : isDone
                      ? "var(--status-connected)"
                      : "var(--text-muted)",
                }}
              >
                {isDone ? <Check size={10} /> : i + 1}
              </div>
              {i < STEP_ORDER.length - 1 && (
                <ChevronRight size={10} color="var(--text-muted)" />
              )}
            </div>
          );
        })}
      </div>

      <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
        <Pause size={14} color="var(--accent-amber, #f59e0b)" />
        <span style={{ fontSize: 13, fontWeight: 600, color: "var(--text-primary)" }}>
          Checkpoint {currentIdx + 1}: {STEP_LABELS[step] ?? step}
        </span>
        {editable && (
          <span
            style={{
              fontSize: 10,
              padding: "2px 6px",
              borderRadius: 3,
              background: "rgba(34, 211, 238, 0.1)",
              color: "var(--accent-cyan)",
              fontWeight: 600,
            }}
          >
            <Edit3 size={9} style={{ marginRight: 3, verticalAlign: "middle" }} />
            editable
          </span>
        )}
      </div>

      <div
        style={{
          background: "var(--bg-primary)",
          border: "1px solid var(--border-secondary)",
          borderRadius: 6,
          padding: 12,
        }}
      >
        {step === "seed" && (
          <SeedReview
            seedText={seedText}
            editable={editable}
            onChange={setSeedText}
            metadata={seedMeta}
          />
        )}
        {step === "ontology" && <OntologyReview data={data} />}
        {step === "graph" && <SimpleMessage text="Graph build complete." />}
        {step === "profiles" && <SimpleMessage text="Profile generation complete." />}
        {step === "config" && (
          <ConfigReview
            maxRounds={maxRounds}
            editable={editable}
            onChange={setMaxRounds}
          />
        )}
      </div>

      <div style={{ display: "flex", gap: 8 }}>
        <button
          onClick={onCancel}
          style={{
            flex: 1,
            padding: "8px 12px",
            background: "transparent",
            border: "1px solid var(--border-secondary)",
            borderRadius: 4,
            color: "var(--text-muted)",
            fontSize: 12,
            fontWeight: 600,
            cursor: "pointer",
          }}
        >
          Cancel
        </button>
        <button
          onClick={handleContinue}
          style={{
            flex: 2,
            padding: "8px 12px",
            background: "var(--accent-cyan)",
            border: "none",
            borderRadius: 4,
            color: "var(--bg-primary)",
            fontSize: 12,
            fontWeight: 700,
            cursor: "pointer",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            gap: 6,
          }}
        >
          <Play size={12} />
          {editable ? "Apply & Continue" : "Continue"}
        </button>
      </div>
    </div>
  );
}

function SeedReview({
  seedText,
  editable,
  onChange,
  metadata,
}: {
  seedText: string;
  editable: boolean;
  onChange: (v: string) => void;
  metadata: {
    vessels_count: number;
    actors_identified: string[];
    resolved_entity_count: number;
    used_observation_ids: string[];
    web_search_count: number;
    tension_score: number;
  } | null;
}) {
  const statStyle = {
    display: "flex",
    justifyContent: "space-between",
    fontSize: 11,
    color: "var(--text-muted)",
    padding: "3px 0",
  } as const;

  const valStyle = {
    fontWeight: 700,
    fontFamily: "monospace",
    color: "var(--text-primary)",
  } as const;

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
      <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
        <Eye size={12} color="var(--text-muted)" />
        <span style={{ fontSize: 11, fontWeight: 600, color: "var(--text-muted)", textTransform: "uppercase", letterSpacing: "0.04em" }}>
          Seed Text
        </span>
      </div>
      {metadata && (
        <div style={{
          display: "grid",
          gridTemplateColumns: "1fr 1fr",
          gap: "2px 16px",
          padding: "8px 10px",
          background: "var(--bg-secondary)",
          border: "1px solid var(--border-secondary)",
          borderRadius: 4,
          marginBottom: 4,
        }}>
          <div style={statStyle}>
            <span>군함</span>
            <span style={valStyle}>{metadata.vessels_count}</span>
          </div>
          <div style={statStyle}>
            <span>긴장도</span>
            <span style={valStyle}>{metadata.tension_score.toFixed(1)}</span>
          </div>
          <div style={statStyle}>
            <span>해소 엔티티</span>
            <span style={{
              ...valStyle,
              color: metadata.resolved_entity_count > 0 ? "var(--accent-cyan)" : "var(--text-muted)",
            }}>{metadata.resolved_entity_count}</span>
          </div>
          <div style={statStyle}>
            <span>관측 사용</span>
            <span style={{
              ...valStyle,
              color: metadata.used_observation_ids.length > 0 ? "var(--accent-cyan)" : "var(--text-muted)",
            }}>{metadata.used_observation_ids.length}</span>
          </div>
          <div style={statStyle}>
            <span>행위자</span>
            <span style={valStyle}>{metadata.actors_identified.length}</span>
          </div>
          <div style={statStyle}>
            <span>웹 검색</span>
            <span style={valStyle}>{metadata.web_search_count}</span>
          </div>
        </div>
      )}
      <textarea
        value={seedText}
        onChange={(e) => onChange(e.target.value)}
        readOnly={!editable}
        rows={8}
        style={{
          width: "100%",
          padding: "8px 10px",
          background: editable ? "var(--bg-secondary)" : "transparent",
          border: editable ? "1px solid var(--accent-cyan)" : "1px solid var(--border-secondary)",
          borderRadius: 4,
          color: "var(--text-primary)",
          fontSize: 12,
          fontFamily: "monospace",
          lineHeight: 1.5,
          resize: "vertical",
          outline: "none",
          cursor: editable ? "text" : "default",
        }}
      />
      {editable && (
        <span style={{ fontSize: 11, color: "var(--text-muted)" }}>
          Edit seed text before proceeding to ontology generation.
        </span>
      )}
    </div>
  );
}

function OntologyReview({ data }: { data: Record<string, unknown> | null }) {
  const entityTypes = (data?.entity_types ?? []) as string[];
  const edgeTypes = (data?.edge_types ?? []) as string[];

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
      <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
        <Eye size={12} color="var(--text-muted)" />
        <span style={{ fontSize: 11, fontWeight: 600, color: "var(--text-muted)", textTransform: "uppercase", letterSpacing: "0.04em" }}>
          Ontology
        </span>
      </div>
      <div style={{ display: "flex", gap: 12 }}>
        <div style={{ flex: 1 }}>
          <div style={{ fontSize: 11, color: "var(--accent-cyan)", fontWeight: 600, marginBottom: 6 }}>
            Entity Types ({entityTypes.length})
          </div>
          <div style={{ display: "flex", flexWrap: "wrap", gap: 4 }}>
            {entityTypes.map((t) => (
              <span
                key={t}
                style={{
                  padding: "2px 8px",
                  background: "rgba(34, 211, 238, 0.08)",
                  border: "1px solid rgba(34, 211, 238, 0.2)",
                  borderRadius: 3,
                  fontSize: 11,
                  color: "var(--text-primary)",
                }}
              >
                {t}
              </span>
            ))}
            {entityTypes.length === 0 && (
              <span style={{ fontSize: 11, color: "var(--text-muted)" }}>None</span>
            )}
          </div>
        </div>
        <div style={{ flex: 1 }}>
          <div style={{ fontSize: 11, color: "var(--accent-cyan)", fontWeight: 600, marginBottom: 6 }}>
            Edge Types ({edgeTypes.length})
          </div>
          <div style={{ display: "flex", flexWrap: "wrap", gap: 4 }}>
            {edgeTypes.map((t) => (
              <span
                key={t}
                style={{
                  padding: "2px 8px",
                  background: "rgba(34, 211, 238, 0.08)",
                  border: "1px solid rgba(34, 211, 238, 0.2)",
                  borderRadius: 3,
                  fontSize: 11,
                  color: "var(--text-primary)",
                }}
              >
                {t}
              </span>
            ))}
            {edgeTypes.length === 0 && (
              <span style={{ fontSize: 11, color: "var(--text-muted)" }}>None</span>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

function SimpleMessage({ text }: { text: string }) {
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 8, padding: "8px 0" }}>
      <Check size={14} color="var(--status-connected)" />
      <span style={{ fontSize: 13, color: "var(--text-primary)" }}>{text}</span>
    </div>
  );
}

function ConfigReview({
  maxRounds,
  editable,
  onChange,
}: {
  maxRounds: number;
  editable: boolean;
  onChange: (v: number) => void;
}) {
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
      <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
        <Eye size={12} color="var(--text-muted)" />
        <span style={{ fontSize: 11, fontWeight: 600, color: "var(--text-muted)", textTransform: "uppercase", letterSpacing: "0.04em" }}>
          Simulation Config
        </span>
      </div>
      <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
        <span style={{ fontSize: 12, color: "var(--text-muted)", whiteSpace: "nowrap" }}>
          Max Rounds:
        </span>
        <input
          type="number"
          min={1}
          max={100}
          value={maxRounds}
          onChange={(e) => onChange(Number(e.target.value))}
          readOnly={!editable}
          style={{
            width: 70,
            padding: "6px 8px",
            background: editable ? "var(--bg-secondary)" : "transparent",
            border: editable ? "1px solid var(--accent-cyan)" : "1px solid var(--border-secondary)",
            borderRadius: 4,
            color: "var(--text-primary)",
            fontSize: 13,
            fontWeight: 600,
            textAlign: "center",
            outline: "none",
          }}
        />
      </div>
      {editable && (
        <span style={{ fontSize: 11, color: "var(--text-muted)" }}>
          Adjust max rounds before starting the simulation run.
        </span>
      )}
    </div>
  );
}
