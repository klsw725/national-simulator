import type React from "react";

export const STATE_VARIABLES = ["threat_perception", "domestic_pressure", "resource_level"];

export const ATTRIBUTION_COLORS = ["#3b82f6", "#8b5cf6", "#f97316", "#22c55e", "#ef4444", "#06b6d4"];

export interface ModelInfo {
  id: string;
  vars: string[];
}

export interface CausalTabProps {
  vars: string[];
  queryError: string | null;
  setQueryError: (error: string | null) => void;
  ensureModel: () => Promise<ModelInfo | null>;
  fitting: boolean;
}

export const inputStyle: React.CSSProperties = {
  width: "100%",
  padding: "6px 8px",
  background: "rgba(255,255,255,0.04)",
  border: "1px solid var(--border-secondary)",
  borderRadius: 4,
  color: "var(--text-primary)",
  fontSize: 12,
  outline: "none",
};

export const selectStyle: React.CSSProperties = {
  ...inputStyle,
  appearance: "none" as const,
  cursor: "pointer",
};

export const buttonStyle: React.CSSProperties = {
  padding: "8px 14px",
  background: "var(--accent-cyan)",
  border: "none",
  borderRadius: 4,
  color: "var(--bg-primary)",
  fontSize: 12,
  fontWeight: 700,
  cursor: "pointer",
  display: "inline-flex",
  alignItems: "center",
  gap: 6,
};
