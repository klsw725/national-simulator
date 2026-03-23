"use client";

interface Anomaly {
  type: string;
  source_type: string;
  detected_at: string;
  severity: string;
  detail: string;
  current: number;
  baseline: number;
  sigma: number;
}

interface AnomalyListProps {
  anomalies: Anomaly[];
}

export default function AnomalyList({ anomalies }: AnomalyListProps) {
  if (anomalies.length === 0) {
    return (
      <div
        style={{
          fontSize: 12,
          color: "rgb(75, 85, 99)",
          textAlign: "center",
          padding: 16,
        }}
      >
        현재 이상 징후 없음
      </div>
    );
  }

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
      {anomalies.map((a, i) => {
        const severityColor =
          a.severity === "high"
            ? "#ef4444"
            : a.severity === "medium"
              ? "#facc15"
              : "#9ca3af";
        const severityDot =
          a.severity === "high"
            ? "\u{1F534}"
            : a.severity === "medium"
              ? "\u{1F7E1}"
              : "\u26AA";
        return (
          <div
            key={i}
            style={{
              padding: "8px 10px",
              background: "rgba(255,255,255,0.03)",
              border: `1px solid ${severityColor}22`,
              borderRadius: 6,
              borderLeft: `3px solid ${severityColor}`,
            }}
          >
            <div
              style={{
                display: "flex",
                alignItems: "center",
                gap: 6,
                marginBottom: 4,
              }}
            >
              <span>{severityDot}</span>
              <span
                style={{
                  fontSize: 10,
                  fontWeight: 600,
                  color: severityColor,
                  textTransform: "uppercase",
                }}
              >
                {a.severity}
              </span>
              <span
                style={{
                  fontSize: 10,
                  color: "rgb(107, 114, 128)",
                  marginLeft: "auto",
                }}
              >
                {a.detected_at.slice(11, 16)} UTC
              </span>
            </div>
            <div style={{ fontSize: 12, color: "#d1d5db", lineHeight: 1.4 }}>
              {a.detail}
            </div>
          </div>
        );
      })}
    </div>
  );
}
