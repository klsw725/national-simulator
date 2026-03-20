"use client";

import dynamic from "next/dynamic";
import { useMemo, useState } from "react";
import { useDataPolling } from "@/hooks/useDataPolling";
import { useSimulation } from "@/hooks/useSimulation";
import {
  buildShipsGeoJSON,
  buildMilitaryFlightsGeoJSON,
  buildSatellitesGeoJSON,
  buildMilitaryBasesGeoJSON,
} from "@/components/map/geoJSONBuilders";
import type { BackendStatus } from "@/types/dashboard";
import { Crosshair } from "lucide-react";
import SimulationPanel from "@/components/simulation/SimulationPanel";
import LayerToggle, { type LayerVisibility } from "@/components/map/LayerToggle";

const MaplibreViewer = dynamic(
  () => import("@/components/map/MaplibreViewer"),
  { ssr: false }
);

function StatusIndicator({ status }: { status: BackendStatus }) {
  const colorMap: Record<BackendStatus, string> = {
    connected: "var(--status-connected)",
    disconnected: "var(--status-disconnected)",
    connecting: "var(--status-connecting)",
  };

  const labelMap: Record<BackendStatus, string> = {
    connected: "LIVE",
    disconnected: "OFFLINE",
    connecting: "CONNECTING",
  };

  return (
    <div
      style={{
        position: "fixed",
        top: 12,
        right: 12,
        zIndex: 10,
        display: "flex",
        alignItems: "center",
        gap: 8,
        padding: "6px 12px",
        background: "rgba(0, 0, 0, 0.75)",
        borderRadius: 6,
        border: "1px solid var(--border-secondary)",
        fontSize: 11,
        fontFamily: "monospace",
        letterSpacing: "0.05em",
      }}
    >
      <span
        style={{
          width: 8,
          height: 8,
          borderRadius: "50%",
          background: colorMap[status],
          boxShadow:
            status === "connected"
              ? `0 0 6px ${colorMap[status]}`
              : undefined,
        }}
      />
      <span style={{ color: colorMap[status] }}>{labelMap[status]}</span>
    </div>
  );
}

const DEFAULT_LAYER_VISIBILITY: LayerVisibility = {
  ships: true,
  militaryFlights: true,
  satellites: true,
  militaryBases: true,
};

export default function HomePage() {
  const { ships, militaryFlights, satellites, militaryBases, backendStatus } = useDataPolling();
  const shipsGeoJSON = useMemo(() => buildShipsGeoJSON(ships), [ships]);
  const militaryFlightsGeoJSON = useMemo(() => buildMilitaryFlightsGeoJSON(militaryFlights), [militaryFlights]);
  const satellitesGeoJSON = useMemo(() => buildSatellitesGeoJSON(satellites), [satellites]);
  const militaryBasesGeoJSON = useMemo(() => buildMilitaryBasesGeoJSON(militaryBases), [militaryBases]);
  const sim = useSimulation();
  const [panelOpen, setPanelOpen] = useState(false);
  const [layerVisibility, setLayerVisibility] = useState<LayerVisibility>(DEFAULT_LAYER_VISIBILITY);

  return (
    <main style={{ width: "100vw", height: "100vh", position: "relative" }}>
      <StatusIndicator status={backendStatus} />
      <MaplibreViewer
        shipsGeoJSON={shipsGeoJSON}
        militaryFlightsGeoJSON={militaryFlightsGeoJSON}
        satellitesGeoJSON={satellitesGeoJSON}
        militaryBasesGeoJSON={militaryBasesGeoJSON}
        simulationGeoJSON={sim.simulationGeoJSON}
        layerVisibility={layerVisibility}
      />
      <LayerToggle visibility={layerVisibility} onChange={setLayerVisibility} />

      <SimulationPanel
        open={panelOpen}
        onClose={() => setPanelOpen(false)}
        sim={sim}
      />

      {!panelOpen && (
        <button
          onClick={() => setPanelOpen(true)}
          style={{
            position: "fixed",
            bottom: 24,
            right: 24,
            zIndex: 15,
            width: 48,
            height: 48,
            borderRadius: "50%",
            background: "var(--accent-cyan)",
            border: "none",
            cursor: "pointer",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            boxShadow: "0 2px 12px rgba(34, 211, 238, 0.3)",
            transition: "transform 0.15s, box-shadow 0.15s",
          }}
          title="시뮬레이션 패널 열기"
        >
          <Crosshair size={22} color="var(--bg-primary)" />
        </button>
      )}
    </main>
  );
}
