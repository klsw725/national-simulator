"use client";

import { useState } from "react";
import type { PollingResult } from "@/hooks/useDataPolling";
import type { OSINTSummary } from "@/hooks/useOSINTSummary";
import type { Ship, Flight, UAV, Satellite, MilitaryBase } from "@/types/dashboard";

interface AssetsTabProps {
  summary: OSINTSummary;
  polling: PollingResult;
  onFlyTo?: (lng: number, lat: number) => void;
}

export default function AssetsTab({ summary, polling, onFlyTo }: AssetsTabProps) {
  const [expanded, setExpanded] = useState<Record<string, boolean>>({});

  const toggle = (key: string) => {
    setExpanded((prev) => ({ ...prev, [key]: !prev[key] }));
  };

  const handleClick = (lat: number, lng: number) => {
    onFlyTo?.(lng, lat);
  };

  const shipsByCountry = groupBy(polling.ships, (s) => s.country);
  const flightsByCountry = groupBy(polling.militaryFlights, (f) => f.country);
  const uavsByCountry = groupBy(polling.uavs, (u) => u.country);

  return (
    <div style={{ padding: "12px 16px", display: "flex", flexDirection: "column", gap: 4 }}>
      {summary.assetsByCountry.map((ac) => {
        const countryKey = ac.country;
        const isExpanded = expanded[countryKey] ?? true;
        const total =
          ac.ships + ac.flights + ac.uavs + ac.satellites + ac.bases;

        return (
          <div key={countryKey}>
            <div
              onClick={() => toggle(countryKey)}
              style={{
                display: "flex",
                alignItems: "center",
                gap: 6,
                padding: "6px 0",
                cursor: "pointer",
                userSelect: "none",
              }}
            >
              <span style={{ fontSize: 10, color: "rgb(107, 114, 128)", width: 10 }}>
                {isExpanded ? "▾" : "▸"}
              </span>
              <span style={{ fontSize: 12, fontWeight: 600, color: "#f3f4f6", flex: 1 }}>
                {countryKey}
              </span>
              <span
                style={{
                  fontSize: 11,
                  color: "rgb(107, 114, 128)",
                  fontVariantNumeric: "tabular-nums",
                }}
              >
                ({total})
              </span>
            </div>

            {isExpanded && (
              <div style={{ paddingLeft: 16, paddingBottom: 8, display: "flex", flexDirection: "column", gap: 2 }}>
                {ac.ships > 0 && (
                  <AssetGroup
                    icon="🚢"
                    label={`군함 ${ac.ships}척`}
                    items={shipsByCountry[countryKey] ?? []}
                    renderItem={(s: Ship) => s.name || `MMSI ${s.mmsi}`}
                    getCoords={(s: Ship) => [s.lat, s.lng]}
                    onFlyTo={handleClick}
                  />
                )}
                {ac.flights > 0 && (
                  <AssetGroup
                    icon="✈️"
                    label={`군용기 ${ac.flights}대`}
                    items={flightsByCountry[countryKey] ?? []}
                    renderItem={(f: Flight) =>
                      `${f.callsign} ${f.model ? `(${f.model})` : ""}`
                    }
                    getCoords={(f: Flight) => [f.lat, f.lng]}
                    onFlyTo={handleClick}
                  />
                )}
                {ac.uavs > 0 && (
                  <AssetGroup
                    icon="🛸"
                    label={`UAV ${ac.uavs}대`}
                    items={uavsByCountry[countryKey] ?? []}
                    renderItem={(u: UAV) =>
                      `${u.aircraft_model} (${u.uav_type})`
                    }
                    getCoords={(u: UAV) => [u.lat, u.lng]}
                    onFlyTo={handleClick}
                  />
                )}
                {ac.bases > 0 && (
                  <AssetGroup
                    icon="🏗️"
                    label={`기지 ${ac.bases}개`}
                    items={polling.militaryBases.filter(
                      (b) => b.country === countryKey
                    )}
                    renderItem={(b: MilitaryBase) => b.name}
                    getCoords={(b: MilitaryBase) => [b.lat, b.lng]}
                    onFlyTo={handleClick}
                  />
                )}
              </div>
            )}
          </div>
        );
      })}

      {polling.satellites.length > 0 && (
        <div>
          <div
            onClick={() => toggle("__satellites__")}
            style={{
              display: "flex",
              alignItems: "center",
              gap: 6,
              padding: "6px 0",
              cursor: "pointer",
              userSelect: "none",
            }}
          >
            <span style={{ fontSize: 10, color: "rgb(107, 114, 128)", width: 10 }}>
              {expanded["__satellites__"] ?? false ? "▾" : "▸"}
            </span>
            <span style={{ fontSize: 12, fontWeight: 600, color: "#f3f4f6", flex: 1 }}>
              🛰️ 정찰 위성
            </span>
            <span
              style={{
                fontSize: 11,
                color: "rgb(107, 114, 128)",
                fontVariantNumeric: "tabular-nums",
              }}
            >
              ({polling.satellites.length})
            </span>
          </div>

          {(expanded["__satellites__"] ?? false) && (
            <div style={{ paddingLeft: 16, paddingBottom: 8, display: "flex", flexDirection: "column", gap: 2 }}>
              {polling.satellites.slice(0, 30).map((sat, i) => (
                <div
                  key={i}
                  onClick={() => handleClick(sat.lat, sat.lng)}
                  style={{
                    fontSize: 11,
                    color: "#d1d5db",
                    cursor: "pointer",
                    padding: "2px 0",
                  }}
                >
                  <span style={{ color: "rgb(107, 114, 128)" }}>
                    {sat.country}
                  </span>{" "}
                  {sat.name}
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function AssetGroup<T>({
  icon,
  label,
  items,
  renderItem,
  getCoords,
  onFlyTo,
}: {
  icon: string;
  label: string;
  items: T[];
  renderItem: (item: T) => string;
  getCoords: (item: T) => [number, number];
  onFlyTo: (lat: number, lng: number) => void;
}) {
  return (
    <div style={{ marginBottom: 4 }}>
      <div style={{ fontSize: 11, color: "rgb(107, 114, 128)", marginBottom: 2 }}>
        {icon} {label}
      </div>
      {items.slice(0, 20).map((item, i) => {
        const [lat, lng] = getCoords(item);
        return (
          <div
            key={i}
            onClick={() => onFlyTo(lat, lng)}
            style={{
              fontSize: 11,
              color: "#d1d5db",
              paddingLeft: 20,
              cursor: "pointer",
              padding: "1px 0 1px 20px",
            }}
          >
            {renderItem(item)}
          </div>
        );
      })}
    </div>
  );
}

function groupBy<T>(items: T[], keyFn: (item: T) => string): Record<string, T[]> {
  const map: Record<string, T[]> = {};
  for (const item of items) {
    const key = keyFn(item);
    if (!key) continue;
    (map[key] ??= []).push(item);
  }
  return map;
}
