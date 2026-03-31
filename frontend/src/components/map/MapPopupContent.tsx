"use client";

export const LAYER_TO_POPUP_TYPE: Record<string, string> = {
  "ship-icons": "ship",
  "military-flights-layer": "flight",
  "satellites-layer": "satellite",
  "military-bases-layer": "base",
  "simulation-actors-layer": "actor",
  "uavs-layer": "uav",
  "tracked-flights-layer": "tracked-flight",
  "kiwisdr-layer": "kiwisdr",
  "gps-jamming-layer": "gps-jamming",
  "earthquakes-layer": "earthquake",
  "power-plants-layer": "power-plant",
  "datacenters-layer": "datacenter",
  "internet-outages-layer": "internet-outage",
};

const stanceColor = (stance: string) => {
  const s = stance.toLowerCase();
  if (s.includes("hostile") || s.includes("aggressive")) return "#ef4444";
  if (s.includes("neutral")) return "#facc15";
  if (s.includes("friendly") || s.includes("cooperative")) return "#22c55e";
  return "#22d3ee";
};

export default function renderPopupContent(type: string, props: Record<string, unknown>) {
  switch (type) {
    case "actor": {
      const actor = String(props.actor ?? "");
      const stance = String(props.stance ?? "");
      const tension_level = Number(props.tension_level) || 0;
      const key_statement = String(props.key_statement ?? "");
      const post_count = Number(props.post_count) || 0;
      const color = String(props.color ?? "var(--accent-cyan)");
      return (
        <>
          <div
            style={{
              fontWeight: 700,
              fontSize: 14,
              marginBottom: 8,
              color,
            }}
          >
            {actor}
          </div>

          <div style={{ display: "flex", alignItems: "center", gap: 6, marginBottom: 6 }}>
            <span
              style={{
                padding: "2px 8px",
                borderRadius: 10,
                fontSize: 10,
                fontWeight: 600,
                background: stanceColor(stance),
                color: "#000",
                textTransform: "uppercase",
              }}
            >
              {stance}
            </span>
            <span style={{ color: "rgb(107, 114, 128)", fontSize: 11 }}>
              posts: {post_count}
            </span>
          </div>

          <div style={{ marginBottom: 6 }}>
            <div
              style={{
                display: "flex",
                justifyContent: "space-between",
                fontSize: 10,
                color: "rgb(107, 114, 128)",
                marginBottom: 3,
              }}
            >
              <span>Tension</span>
              <span>{(tension_level * 100).toFixed(0)}%</span>
            </div>
            <div
              style={{
                height: 4,
                borderRadius: 2,
                background: "rgba(255,255,255,0.1)",
                overflow: "hidden",
              }}
            >
              <div
                style={{
                  height: "100%",
                  width: `${tension_level * 100}%`,
                  borderRadius: 2,
                  background:
                    tension_level > 0.7
                      ? "#ef4444"
                      : tension_level > 0.4
                        ? "#facc15"
                        : "#22c55e",
                }}
              />
            </div>
          </div>

          {key_statement && (
            <div
              style={{
                marginTop: 8,
                padding: "6px 8px",
                background: "rgba(255,255,255,0.05)",
                borderRadius: 4,
                borderLeft: `3px solid ${color}`,
                fontSize: 11,
                fontStyle: "italic",
                color: "rgb(209, 213, 219)",
              }}
            >
              {key_statement}
            </div>
          )}
        </>
      );
    }

    case "ship": {
      const name = String(props.name ?? "Unknown");
      const shipType = String(props.type ?? "unknown");
      const mmsi = String(props.id ?? "");
      const sog = Number(props.sog) || 0;
      const country = String(props.country ?? "");
      return (
        <>
          <div
            style={{
              fontWeight: 700,
              fontSize: 14,
              marginBottom: 6,
              color: "#22d3ee",
            }}
          >
            {name}
          </div>
          <div style={{ display: "flex", alignItems: "center", gap: 6, marginBottom: 8 }}>
            <span
              style={{
                padding: "2px 8px",
                borderRadius: 10,
                fontSize: 10,
                fontWeight: 600,
                background: shipType === "military_vessel" ? "#facc15" : "#3b82f6",
                color: "#000",
                textTransform: "uppercase",
              }}
            >
              {shipType.replace(/_/g, " ")}
            </span>
          </div>
          <div style={{ display: "flex", flexDirection: "column", gap: 3, fontSize: 11 }}>
            <div style={{ display: "flex", justifyContent: "space-between" }}>
              <span style={{ color: "rgb(107, 114, 128)" }}>MMSI</span>
              <span>{mmsi}</span>
            </div>
            <div style={{ display: "flex", justifyContent: "space-between" }}>
              <span style={{ color: "rgb(107, 114, 128)" }}>SOG</span>
              <span>{sog.toFixed(1)} kn</span>
            </div>
            <div style={{ display: "flex", justifyContent: "space-between" }}>
              <span style={{ color: "rgb(107, 114, 128)" }}>Country</span>
              <span>{country || "Unknown"}</span>
            </div>
          </div>
        </>
      );
    }

    case "flight": {
      const callsign = String(props.callsign ?? "");
      const country = String(props.country ?? "");
      const force = String(props.force ?? "");
      const military_type = String(props.military_type ?? "");
      const model = String(props.model ?? "");
      const alt = Number(props.alt) || 0;
      const speed_knots = Number(props.speed_knots) || 0;
      return (
        <>
          <div
            style={{
              fontWeight: 700,
              fontSize: 14,
              marginBottom: 6,
              color: "#f97316",
            }}
          >
            {callsign}
          </div>
          {force && (
            <div style={{ display: "flex", alignItems: "center", gap: 6, marginBottom: 8 }}>
              <span
                style={{
                  padding: "2px 8px",
                  borderRadius: 10,
                  fontSize: 10,
                  fontWeight: 600,
                  background: "#f97316",
                  color: "#000",
                  textTransform: "uppercase",
                }}
              >
                {force}
              </span>
              {military_type && (
                <span style={{ color: "rgb(107, 114, 128)", fontSize: 11 }}>
                  {military_type}
                </span>
              )}
            </div>
          )}
          <div style={{ display: "flex", flexDirection: "column", gap: 3, fontSize: 11 }}>
            <div style={{ display: "flex", justifyContent: "space-between" }}>
              <span style={{ color: "rgb(107, 114, 128)" }}>Model</span>
              <span>{model || "Unknown"}</span>
            </div>
            <div style={{ display: "flex", justifyContent: "space-between" }}>
              <span style={{ color: "rgb(107, 114, 128)" }}>Altitude</span>
              <span>{alt.toLocaleString()} ft</span>
            </div>
            <div style={{ display: "flex", justifyContent: "space-between" }}>
              <span style={{ color: "rgb(107, 114, 128)" }}>Speed</span>
              <span>{speed_knots.toFixed(0)} kn</span>
            </div>
            <div style={{ display: "flex", justifyContent: "space-between" }}>
              <span style={{ color: "rgb(107, 114, 128)" }}>Country</span>
              <span>{country || "Unknown"}</span>
            </div>
          </div>
        </>
      );
    }

    case "satellite": {
      const name = String(props.name ?? "");
      const country = String(props.country ?? "");
      const mission = String(props.mission ?? "");
      const sat_type = String(props.sat_type ?? "");
      const alt_km = Number(props.alt_km) || 0;
      return (
        <>
          <div
            style={{
              fontWeight: 700,
              fontSize: 14,
              marginBottom: 6,
              color: "#a855f7",
            }}
          >
            {name}
          </div>
          <div style={{ display: "flex", alignItems: "center", gap: 6, marginBottom: 8 }}>
            <span
              style={{
                padding: "2px 8px",
                borderRadius: 10,
                fontSize: 10,
                fontWeight: 600,
                background: "#a855f7",
                color: "#000",
                textTransform: "uppercase",
              }}
            >
              {sat_type}
            </span>
          </div>
          <div style={{ display: "flex", flexDirection: "column", gap: 3, fontSize: 11 }}>
            <div style={{ display: "flex", justifyContent: "space-between" }}>
              <span style={{ color: "rgb(107, 114, 128)" }}>Mission</span>
              <span>{mission || "Unknown"}</span>
            </div>
            <div style={{ display: "flex", justifyContent: "space-between" }}>
              <span style={{ color: "rgb(107, 114, 128)" }}>Altitude</span>
              <span>{alt_km.toLocaleString()} km</span>
            </div>
            <div style={{ display: "flex", justifyContent: "space-between" }}>
              <span style={{ color: "rgb(107, 114, 128)" }}>Country</span>
              <span>{country || "Unknown"}</span>
            </div>
          </div>
        </>
      );
    }

    case "base": {
      const name = String(props.name ?? "");
      const country = String(props.country ?? "");
      const branch = String(props.branch ?? "");
      const operator = String(props.operator ?? "");
      return (
        <>
          <div
            style={{
              fontWeight: 700,
              fontSize: 14,
              marginBottom: 6,
              color: "#ef4444",
            }}
          >
            {name}
          </div>
          <div style={{ display: "flex", alignItems: "center", gap: 6, marginBottom: 8 }}>
            <span
              style={{
                padding: "2px 8px",
                borderRadius: 10,
                fontSize: 10,
                fontWeight: 600,
                background: "#ef4444",
                color: "#000",
                textTransform: "uppercase",
              }}
            >
              {branch}
            </span>
          </div>
          <div style={{ display: "flex", flexDirection: "column", gap: 3, fontSize: 11 }}>
            <div style={{ display: "flex", justifyContent: "space-between" }}>
              <span style={{ color: "rgb(107, 114, 128)" }}>Operator</span>
              <span>{operator || "Unknown"}</span>
            </div>
            <div style={{ display: "flex", justifyContent: "space-between" }}>
              <span style={{ color: "rgb(107, 114, 128)" }}>Country</span>
              <span>{country || "Unknown"}</span>
            </div>
          </div>
        </>
      );
    }

    case "uav": {
      const callsign = String(props.callsign ?? "");
      const country = String(props.country ?? "");
      const model = String(props.model ?? "");
      const alt = Number(props.alt) || 0;
      const speed_knots = Number(props.speed_knots) || 0;
      return (
        <>
          <div
            style={{
              fontWeight: 700,
              fontSize: 14,
              marginBottom: 6,
              color: "#eab308",
            }}
          >
            {callsign}
          </div>
          <div style={{ display: "flex", flexDirection: "column", gap: 3, fontSize: 11 }}>
            <div style={{ display: "flex", justifyContent: "space-between" }}>
              <span style={{ color: "rgb(107, 114, 128)" }}>Model</span>
              <span>{model || "Unknown"}</span>
            </div>
            <div style={{ display: "flex", justifyContent: "space-between" }}>
              <span style={{ color: "rgb(107, 114, 128)" }}>Altitude</span>
              <span>{alt.toLocaleString()} ft</span>
            </div>
            <div style={{ display: "flex", justifyContent: "space-between" }}>
              <span style={{ color: "rgb(107, 114, 128)" }}>Speed</span>
              <span>{speed_knots.toFixed(0)} kn</span>
            </div>
            <div style={{ display: "flex", justifyContent: "space-between" }}>
              <span style={{ color: "rgb(107, 114, 128)" }}>Country</span>
              <span>{country || "Unknown"}</span>
            </div>
          </div>
        </>
      );
    }

    case "tracked-flight": {
      const callsign = String(props.callsign ?? "");
      const country = String(props.country ?? "");
      const model = String(props.model ?? "");
      const alt = Number(props.alt) || 0;
      const speed_knots = Number(props.speed_knots) || 0;
      const airline = String(props.airline ?? "");
      return (
        <>
          <div
            style={{
              fontWeight: 700,
              fontSize: 14,
              marginBottom: 6,
              color: "#ec4899",
            }}
          >
            {callsign}
          </div>
          {airline && (
            <div style={{ display: "flex", alignItems: "center", gap: 6, marginBottom: 8 }}>
              <span
                style={{
                  padding: "2px 8px",
                  borderRadius: 10,
                  fontSize: 10,
                  fontWeight: 600,
                  background: "#ec4899",
                  color: "#000",
                  textTransform: "uppercase",
                }}
              >
                {airline}
              </span>
            </div>
          )}
          <div style={{ display: "flex", flexDirection: "column", gap: 3, fontSize: 11 }}>
            <div style={{ display: "flex", justifyContent: "space-between" }}>
              <span style={{ color: "rgb(107, 114, 128)" }}>Model</span>
              <span>{model || "Unknown"}</span>
            </div>
            <div style={{ display: "flex", justifyContent: "space-between" }}>
              <span style={{ color: "rgb(107, 114, 128)" }}>Altitude</span>
              <span>{alt.toLocaleString()} ft</span>
            </div>
            <div style={{ display: "flex", justifyContent: "space-between" }}>
              <span style={{ color: "rgb(107, 114, 128)" }}>Speed</span>
              <span>{speed_knots.toFixed(0)} kn</span>
            </div>
            <div style={{ display: "flex", justifyContent: "space-between" }}>
              <span style={{ color: "rgb(107, 114, 128)" }}>Country</span>
              <span>{country || "Unknown"}</span>
            </div>
          </div>
        </>
      );
    }

    case "kiwisdr": {
      const location_name = String(props.location_name ?? "");
      const frequency = String(props.frequency ?? "");
      const band = String(props.band ?? "");
      return (
        <>
          <div
            style={{
              fontWeight: 700,
              fontSize: 14,
              marginBottom: 6,
              color: "#14b8a6",
            }}
          >
            {location_name}
          </div>
          <div style={{ display: "flex", flexDirection: "column", gap: 3, fontSize: 11 }}>
            <div style={{ display: "flex", justifyContent: "space-between" }}>
              <span style={{ color: "rgb(107, 114, 128)" }}>Frequency</span>
              <span>{frequency || "\u2014"}</span>
            </div>
            <div style={{ display: "flex", justifyContent: "space-between" }}>
              <span style={{ color: "rgb(107, 114, 128)" }}>Band</span>
              <span>{band || "\u2014"}</span>
            </div>
          </div>
        </>
      );
    }

    case "gps-jamming": {
      const severity = Number(props.severity) || 0;
      const source = String(props.source ?? "");
      const region = String(props.region ?? "");
      const affected_area_km = Number(props.affected_area_km) || 0;
      return (
        <>
          <div
            style={{
              fontWeight: 700,
              fontSize: 14,
              marginBottom: 6,
              color: "#dc2626",
            }}
          >
            GPS Jamming
          </div>
          <div style={{ display: "flex", alignItems: "center", gap: 6, marginBottom: 8 }}>
            <span
              style={{
                padding: "2px 8px",
                borderRadius: 10,
                fontSize: 10,
                fontWeight: 600,
                background: "#dc2626",
                color: "#000",
                textTransform: "uppercase",
              }}
            >
              Severity: {severity}
            </span>
          </div>
          <div style={{ display: "flex", flexDirection: "column", gap: 3, fontSize: 11 }}>
            <div style={{ display: "flex", justifyContent: "space-between" }}>
              <span style={{ color: "rgb(107, 114, 128)" }}>Region</span>
              <span>{region || "Unknown"}</span>
            </div>
            <div style={{ display: "flex", justifyContent: "space-between" }}>
              <span style={{ color: "rgb(107, 114, 128)" }}>Source</span>
              <span>{source || "Unknown"}</span>
            </div>
            <div style={{ display: "flex", justifyContent: "space-between" }}>
              <span style={{ color: "rgb(107, 114, 128)" }}>Area</span>
              <span>{affected_area_km.toLocaleString()} km</span>
            </div>
          </div>
        </>
      );
    }

    case "earthquake": {
      const place = String(props.place ?? "");
      const mag = Number(props.mag) || 0;
      const depth_km = Number(props.depth_km) || 0;
      const time = String(props.time ?? "");
      return (
        <>
          <div
            style={{
              fontWeight: 700,
              fontSize: 14,
              marginBottom: 6,
              color: "#b91c1c",
            }}
          >
            {place}
          </div>
          <div style={{ display: "flex", alignItems: "center", gap: 6, marginBottom: 8 }}>
            <span
              style={{
                padding: "2px 8px",
                borderRadius: 10,
                fontSize: 10,
                fontWeight: 600,
                background: "#b91c1c",
                color: "#fff",
                textTransform: "uppercase",
              }}
            >
              M {mag.toFixed(1)}
            </span>
          </div>
          <div style={{ display: "flex", flexDirection: "column", gap: 3, fontSize: 11 }}>
            <div style={{ display: "flex", justifyContent: "space-between" }}>
              <span style={{ color: "rgb(107, 114, 128)" }}>Depth</span>
              <span>{depth_km.toFixed(1)} km</span>
            </div>
            <div style={{ display: "flex", justifyContent: "space-between" }}>
              <span style={{ color: "rgb(107, 114, 128)" }}>Time</span>
              <span>{time || "\u2014"}</span>
            </div>
          </div>
        </>
      );
    }

    case "power-plant": {
      const name = String(props.name ?? "");
      const fuel_type = String(props.fuel_type ?? "");
      const capacity_mw = Number(props.capacity_mw) || 0;
      const country = String(props.country ?? "");
      return (
        <>
          <div
            style={{
              fontWeight: 700,
              fontSize: 14,
              marginBottom: 6,
              color: "#f59e0b",
            }}
          >
            {name}
          </div>
          <div style={{ display: "flex", alignItems: "center", gap: 6, marginBottom: 8 }}>
            <span
              style={{
                padding: "2px 8px",
                borderRadius: 10,
                fontSize: 10,
                fontWeight: 600,
                background: "#f59e0b",
                color: "#000",
                textTransform: "uppercase",
              }}
            >
              {fuel_type}
            </span>
          </div>
          <div style={{ display: "flex", flexDirection: "column", gap: 3, fontSize: 11 }}>
            <div style={{ display: "flex", justifyContent: "space-between" }}>
              <span style={{ color: "rgb(107, 114, 128)" }}>Capacity</span>
              <span>{capacity_mw.toLocaleString()} MW</span>
            </div>
            <div style={{ display: "flex", justifyContent: "space-between" }}>
              <span style={{ color: "rgb(107, 114, 128)" }}>Country</span>
              <span>{country || "Unknown"}</span>
            </div>
          </div>
        </>
      );
    }

    case "datacenter": {
      const name = String(props.name ?? "");
      const operator = String(props.operator ?? "");
      const country = String(props.country ?? "");
      return (
        <>
          <div
            style={{
              fontWeight: 700,
              fontSize: 14,
              marginBottom: 6,
              color: "#6366f1",
            }}
          >
            {name}
          </div>
          <div style={{ display: "flex", flexDirection: "column", gap: 3, fontSize: 11 }}>
            <div style={{ display: "flex", justifyContent: "space-between" }}>
              <span style={{ color: "rgb(107, 114, 128)" }}>Operator</span>
              <span>{operator || "Unknown"}</span>
            </div>
            <div style={{ display: "flex", justifyContent: "space-between" }}>
              <span style={{ color: "rgb(107, 114, 128)" }}>Country</span>
              <span>{country || "Unknown"}</span>
            </div>
          </div>
        </>
      );
    }

    case "internet-outage": {
      const region_name = String(props.region_name ?? "");
      const severity = Number(props.severity) || 0;
      const provider = String(props.provider ?? "");
      const affected_users = Number(props.affected_users) || 0;
      return (
        <>
          <div
            style={{
              fontWeight: 700,
              fontSize: 14,
              marginBottom: 6,
              color: "#7c3aed",
            }}
          >
            {region_name}
          </div>
          <div style={{ display: "flex", alignItems: "center", gap: 6, marginBottom: 8 }}>
            <span
              style={{
                padding: "2px 8px",
                borderRadius: 10,
                fontSize: 10,
                fontWeight: 600,
                background: "#7c3aed",
                color: "#fff",
                textTransform: "uppercase",
              }}
            >
              Severity: {severity}
            </span>
          </div>
          <div style={{ display: "flex", flexDirection: "column", gap: 3, fontSize: 11 }}>
            <div style={{ display: "flex", justifyContent: "space-between" }}>
              <span style={{ color: "rgb(107, 114, 128)" }}>Provider</span>
              <span>{provider || "Unknown"}</span>
            </div>
            <div style={{ display: "flex", justifyContent: "space-between" }}>
              <span style={{ color: "rgb(107, 114, 128)" }}>Affected Users</span>
              <span>{affected_users.toLocaleString()}</span>
            </div>
          </div>
        </>
      );
    }

    default:
      return null;
  }
}
