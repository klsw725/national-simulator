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
  buildUAVsGeoJSON,
  buildTrackedFlightsGeoJSON,
  buildCCTVGeoJSON,
  buildKiwiSDRGeoJSON,
  buildGPSJammingGeoJSON,
  buildEarthquakesGeoJSON,
  buildFiresGeoJSON,
  buildPowerPlantsGeoJSON,
  buildDatacentersGeoJSON,
  buildInternetOutagesGeoJSON,
} from "@/components/map/geoJSONBuilders";
import type { BackendStatus } from "@/types/dashboard";
import { Crosshair, Radio } from "lucide-react";
import LayerToggle, { type LayerVisibility } from "@/components/map/LayerToggle";
import { useOSINTSummary } from "@/hooks/useOSINTSummary";

const MaplibreViewer = dynamic(
  () => import("@/components/map/MaplibreViewer"),
  { ssr: false }
);

const SimulationPanel = dynamic(
  () => import("@/components/simulation/SimulationPanel"),
  { ssr: false }
);

const OSINTPanel = dynamic(
  () => import("@/components/osint/OSINTPanel"),
  { ssr: false }
);

const WhatIfCompareModal = dynamic(
  () => import("@/components/simulation/WhatIfCompareModal"),
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
  uavs: true,
  trackedFlights: true,
  gpsJamming: true,
  cctv: false,
  powerPlants: false,
  datacenters: false,
  kiwisdr: false,
  earthquakes: false,
  firmsFires: false,
  internetOutages: false,
};

export default function HomePage() {
  const polling = useDataPolling();
  const {
    ships,
    militaryFlights,
    satellites,
    militaryBases,
    uavs,
    trackedFlights,
    cctv,
    gpsJamming,
    earthquakes,
    kiwisdr,
    firmsFires,
    powerPlants,
    datacenters,
    internetOutages,
    backendStatus,
  } = polling;

  const shipsGeoJSON = useMemo(() => buildShipsGeoJSON(ships), [ships]);
  const militaryFlightsGeoJSON = useMemo(() => buildMilitaryFlightsGeoJSON(militaryFlights), [militaryFlights]);
  const satellitesGeoJSON = useMemo(() => buildSatellitesGeoJSON(satellites), [satellites]);
  const militaryBasesGeoJSON = useMemo(() => buildMilitaryBasesGeoJSON(militaryBases), [militaryBases]);
  const uavsGeoJSON = useMemo(() => buildUAVsGeoJSON(uavs), [uavs]);
  const trackedFlightsGeoJSON = useMemo(() => buildTrackedFlightsGeoJSON(trackedFlights), [trackedFlights]);
  const cctvGeoJSON = useMemo(() => buildCCTVGeoJSON(cctv), [cctv]);
  const kiwisdrGeoJSON = useMemo(() => buildKiwiSDRGeoJSON(kiwisdr), [kiwisdr]);
  const gpsJammingGeoJSON = useMemo(() => buildGPSJammingGeoJSON(gpsJamming), [gpsJamming]);
  const earthquakesGeoJSON = useMemo(() => buildEarthquakesGeoJSON(earthquakes), [earthquakes]);
  const firesGeoJSON = useMemo(() => buildFiresGeoJSON(firmsFires), [firmsFires]);
  const powerPlantsGeoJSON = useMemo(() => buildPowerPlantsGeoJSON(powerPlants), [powerPlants]);
  const datacentersGeoJSON = useMemo(() => buildDatacentersGeoJSON(datacenters), [datacenters]);
  const internetOutagesGeoJSON = useMemo(() => buildInternetOutagesGeoJSON(internetOutages), [internetOutages]);

  const sim = useSimulation();
  const summary = useOSINTSummary(polling);
  const [panelOpen, setPanelOpen] = useState(false);
  const [osintPanelOpen, setOsintPanelOpen] = useState(false);
  const [whatIfCompareBranchId, setWhatIfCompareBranchId] = useState<string | null>(null);
  const [layerVisibility, setLayerVisibility] = useState<LayerVisibility>(DEFAULT_LAYER_VISIBILITY);

  const layerCounts: Partial<Record<keyof LayerVisibility, number>> = useMemo(
    () => ({
      ships: ships.length,
      militaryFlights: militaryFlights.length,
      satellites: satellites.length,
      militaryBases: militaryBases.length,
      uavs: uavs.length,
      trackedFlights: trackedFlights.length,
      cctv: cctv.length,
      gpsJamming: gpsJamming.length,
      earthquakes: earthquakes.length,
      kiwisdr: kiwisdr.length,
      firmsFires: firmsFires.length,
      powerPlants: powerPlants.length,
      datacenters: datacenters.length,
      internetOutages: internetOutages.length,
    }),
    [
      ships.length,
      militaryFlights.length,
      satellites.length,
      militaryBases.length,
      uavs.length,
      trackedFlights.length,
      cctv.length,
      gpsJamming.length,
      earthquakes.length,
      kiwisdr.length,
      firmsFires.length,
      powerPlants.length,
      datacenters.length,
      internetOutages.length,
    ]
  );

  return (
    <main style={{ width: "100vw", height: "100vh", position: "relative" }}>
      <StatusIndicator status={backendStatus} />
      <MaplibreViewer
        shipsGeoJSON={shipsGeoJSON}
        militaryFlightsGeoJSON={militaryFlightsGeoJSON}
        satellitesGeoJSON={satellitesGeoJSON}
        militaryBasesGeoJSON={militaryBasesGeoJSON}
        uavsGeoJSON={uavsGeoJSON}
        trackedFlightsGeoJSON={trackedFlightsGeoJSON}
        cctvGeoJSON={cctvGeoJSON}
        kiwisdrGeoJSON={kiwisdrGeoJSON}
        gpsJammingGeoJSON={gpsJammingGeoJSON}
        earthquakesGeoJSON={earthquakesGeoJSON}
        firesGeoJSON={firesGeoJSON}
        powerPlantsGeoJSON={powerPlantsGeoJSON}
        datacentersGeoJSON={datacentersGeoJSON}
        internetOutagesGeoJSON={internetOutagesGeoJSON}
        simulationGeoJSON={sim.simulationGeoJSON}
        layerVisibility={layerVisibility}
      />
      <LayerToggle
        visibility={layerVisibility}
        onChange={setLayerVisibility}
        counts={layerCounts}
      />

      <OSINTPanel
        open={osintPanelOpen}
        onClose={() => setOsintPanelOpen(false)}
        polling={polling}
        summary={summary}
      />

      <SimulationPanel
        open={panelOpen}
        onClose={() => setPanelOpen(false)}
        sim={sim}
        onOpenWhatIfCompare={(branchId) => setWhatIfCompareBranchId(branchId)}
      />

      {whatIfCompareBranchId && sim.activeScenario && (
        <WhatIfCompareModal
          scenarioId={sim.activeScenario.id}
          branchId={whatIfCompareBranchId}
          onClose={() => setWhatIfCompareBranchId(null)}
        />
      )}

      {!osintPanelOpen && (
        <button
          onClick={() => setOsintPanelOpen(true)}
          style={{
            position: "fixed",
            bottom: 80,
            left: 24,
            zIndex: 15,
            width: 48,
            height: 48,
            borderRadius: "50%",
            background: "#14b8a6",
            border: "none",
            cursor: "pointer",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            boxShadow: "0 2px 12px rgba(20, 184, 166, 0.3)",
            transition: "transform 0.15s, box-shadow 0.15s",
          }}
          title="OSINT 패널 열기"
        >
          <Radio size={22} color="var(--bg-primary)" />
        </button>
      )}

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
