"use client";

import { useState } from "react";

export interface LayerVisibility {
  ships: boolean;
  militaryFlights: boolean;
  satellites: boolean;
  militaryBases: boolean;
  uavs: boolean;
  trackedFlights: boolean;
  gpsJamming: boolean;
  cctv: boolean;
  powerPlants: boolean;
  datacenters: boolean;
  kiwisdr: boolean;
  earthquakes: boolean;
  firmsFires: boolean;
  internetOutages: boolean;
}

interface LayerDef {
  key: keyof LayerVisibility;
  label: string;
  color: string;
}

interface CategoryDef {
  id: string;
  label: string;
  layers: LayerDef[];
  counts?: Record<string, number>;
}

const CATEGORIES: CategoryDef[] = [
  {
    id: "military",
    label: "군사",
    layers: [
      { key: "ships", label: "선박", color: "#22d3ee" },
      { key: "militaryFlights", label: "군용기", color: "#f97316" },
      { key: "uavs", label: "UAV", color: "#eab308" },
      { key: "trackedFlights", label: "추적기", color: "#ec4899" },
      { key: "satellites", label: "위성", color: "#a855f7" },
      { key: "militaryBases", label: "기지", color: "#ef4444" },
      { key: "gpsJamming", label: "GPS 재밍", color: "#dc2626" },
    ],
  },
  {
    id: "infra",
    label: "인프라",
    layers: [
      { key: "powerPlants", label: "발전소", color: "#f59e0b" },
      { key: "datacenters", label: "데이터센터", color: "#6366f1" },
      { key: "cctv", label: "CCTV", color: "#78716c" },
    ],
  },
  {
    id: "sigint",
    label: "SIGINT",
    layers: [{ key: "kiwisdr", label: "KiwiSDR", color: "#14b8a6" }],
  },
  {
    id: "environment",
    label: "환경",
    layers: [
      { key: "earthquakes", label: "지진", color: "#b91c1c" },
      { key: "firmsFires", label: "화재", color: "#ea580c" },
    ],
  },
  {
    id: "info",
    label: "정보",
    layers: [
      { key: "internetOutages", label: "인터넷 장애", color: "#7c3aed" },
    ],
  },
];

interface LayerToggleProps {
  visibility: LayerVisibility;
  onChange: (visibility: LayerVisibility) => void;
  counts?: Partial<Record<keyof LayerVisibility, number>>;
}

export default function LayerToggle({
  visibility,
  onChange,
  counts,
}: LayerToggleProps) {
  const [collapsed, setCollapsed] = useState<Record<string, boolean>>({});

  const toggleLayer = (key: keyof LayerVisibility) => {
    onChange({ ...visibility, [key]: !visibility[key] });
  };

  const toggleCategory = (cat: CategoryDef) => {
    const allOn = cat.layers.every((l) => visibility[l.key]);
    const next = { ...visibility };
    for (const l of cat.layers) {
      next[l.key] = !allOn;
    }
    onChange(next);
  };

  const toggleCollapse = (catId: string) => {
    setCollapsed((prev) => ({ ...prev, [catId]: !prev[catId] }));
  };

  return (
    <div
      style={{
        position: "fixed",
        bottom: 24,
        left: 24,
        zIndex: 15,
        background: "rgba(12, 14, 18, 0.92)",
        border: "1px solid var(--border-secondary)",
        borderRadius: 8,
        padding: "10px 14px",
        display: "flex",
        flexDirection: "column",
        gap: 4,
        backdropFilter: "blur(8px)",
        maxHeight: "calc(100vh - 120px)",
        overflowY: "auto",
      }}
    >
      <div
        style={{
          fontSize: 10,
          fontWeight: 600,
          color: "rgb(107, 114, 128)",
          textTransform: "uppercase",
          letterSpacing: "0.06em",
          marginBottom: 2,
        }}
      >
        Layers
      </div>

      {CATEGORIES.map((cat) => {
        const catLayerKeys = cat.layers.map((l) => l.key);
        const allOn = catLayerKeys.every((k) => visibility[k]);
        const someOn =
          !allOn && catLayerKeys.some((k) => visibility[k]);
        const isCollapsed = collapsed[cat.id] ?? false;

        return (
          <div key={cat.id} style={{ marginBottom: 2 }}>
            <div
              style={{
                display: "flex",
                alignItems: "center",
                gap: 6,
                cursor: "pointer",
                userSelect: "none",
                padding: "3px 0",
              }}
            >
              <span
                onClick={() => toggleCollapse(cat.id)}
                style={{
                  fontSize: 9,
                  color: "rgb(107, 114, 128)",
                  width: 10,
                  display: "inline-flex",
                  justifyContent: "center",
                }}
              >
                {isCollapsed ? "▸" : "▾"}
              </span>
              <span
                onClick={() => toggleCategory(cat)}
                style={{
                  width: 12,
                  height: 12,
                  borderRadius: 2,
                  border: `1.5px solid ${allOn ? "#f3f4f6" : "rgb(75, 85, 99)"}`,
                  background: allOn
                    ? "#f3f4f6"
                    : someOn
                      ? "rgb(75, 85, 99)"
                      : "transparent",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  flexShrink: 0,
                }}
              >
                {(allOn || someOn) && (
                  <svg width="8" height="8" viewBox="0 0 10 10" fill="none">
                    <path
                      d={allOn ? "M2 5l2.5 2.5L8 3" : "M3 5h4"}
                      stroke="rgb(12, 14, 18)"
                      strokeWidth="1.5"
                      strokeLinecap="round"
                      strokeLinejoin="round"
                    />
                  </svg>
                )}
              </span>
              <span
                onClick={() => toggleCollapse(cat.id)}
                style={{
                  fontSize: 11,
                  fontWeight: 600,
                  color: allOn || someOn ? "#f3f4f6" : "rgb(107, 114, 128)",
                  flex: 1,
                }}
              >
                {cat.label}
              </span>
            </div>

            {!isCollapsed &&
              cat.layers.map(({ key, label, color }) => (
                <label
                  key={key}
                  style={{
                    display: "flex",
                    alignItems: "center",
                    gap: 8,
                    cursor: "pointer",
                    fontSize: 11,
                    color: visibility[key]
                      ? "#f3f4f6"
                      : "rgb(107, 114, 128)",
                    userSelect: "none",
                    paddingLeft: 22,
                    paddingTop: 2,
                    paddingBottom: 2,
                  }}
                >
                  <span
                    onClick={() => toggleLayer(key)}
                    style={{
                      width: 12,
                      height: 12,
                      borderRadius: 2,
                      border: `1.5px solid ${visibility[key] ? color : "rgb(75, 85, 99)"}`,
                      background: visibility[key] ? color : "transparent",
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "center",
                      flexShrink: 0,
                      transition: "background 0.15s, border-color 0.15s",
                    }}
                  >
                    {visibility[key] && (
                      <svg
                        width="8"
                        height="8"
                        viewBox="0 0 10 10"
                        fill="none"
                      >
                        <path
                          d="M2 5l2.5 2.5L8 3"
                          stroke="rgb(12, 14, 18)"
                          strokeWidth="1.5"
                          strokeLinecap="round"
                          strokeLinejoin="round"
                        />
                      </svg>
                    )}
                  </span>
                  <span onClick={() => toggleLayer(key)} style={{ flex: 1 }}>
                    {label}
                  </span>
                  {counts?.[key] != null && (
                    <span
                      style={{
                        fontSize: 10,
                        color: "rgb(107, 114, 128)",
                        fontVariantNumeric: "tabular-nums",
                      }}
                    >
                      {counts[key]}
                    </span>
                  )}
                </label>
              ))}
          </div>
        );
      })}
    </div>
  );
}
