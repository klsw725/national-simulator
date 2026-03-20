"use client";

export interface LayerVisibility {
  ships: boolean;
  militaryFlights: boolean;
  satellites: boolean;
  militaryBases: boolean;
}

interface LayerToggleProps {
  visibility: LayerVisibility;
  onChange: (visibility: LayerVisibility) => void;
}

const LAYERS: { key: keyof LayerVisibility; label: string; color: string }[] = [
  { key: "ships", label: "Ships", color: "#22d3ee" },
  { key: "militaryFlights", label: "Military Flights", color: "#f97316" },
  { key: "satellites", label: "Satellites", color: "#a855f7" },
  { key: "militaryBases", label: "Military Bases", color: "#ef4444" },
];

export default function LayerToggle({ visibility, onChange }: LayerToggleProps) {
  const toggle = (key: keyof LayerVisibility) => {
    onChange({ ...visibility, [key]: !visibility[key] });
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
        gap: 6,
        backdropFilter: "blur(8px)",
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
      {LAYERS.map(({ key, label, color }) => (
        <label
          key={key}
          style={{
            display: "flex",
            alignItems: "center",
            gap: 8,
            cursor: "pointer",
            fontSize: 12,
            color: visibility[key] ? "#f3f4f6" : "rgb(107, 114, 128)",
            userSelect: "none",
          }}
        >
          <span
            onClick={() => toggle(key)}
            style={{
              width: 14,
              height: 14,
              borderRadius: 3,
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
              <svg width="10" height="10" viewBox="0 0 10 10" fill="none">
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
          <span onClick={() => toggle(key)}>{label}</span>
        </label>
      ))}
    </div>
  );
}
