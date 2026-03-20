"use client";

import dynamic from "next/dynamic";
import { useMemo } from "react";
import { useDataPolling } from "@/hooks/useDataPolling";
import { buildShipsGeoJSON } from "@/components/map/geoJSONBuilders";
import type { BackendStatus } from "@/types/dashboard";

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

export default function HomePage() {
  const { ships, backendStatus } = useDataPolling();
  const shipsGeoJSON = useMemo(() => buildShipsGeoJSON(ships), [ships]);

  return (
    <main style={{ width: "100vw", height: "100vh", position: "relative" }}>
      <StatusIndicator status={backendStatus} />
      <MaplibreViewer shipsGeoJSON={shipsGeoJSON} />
    </main>
  );
}
