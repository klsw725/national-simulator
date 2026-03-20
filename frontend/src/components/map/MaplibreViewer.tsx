"use client";

import { useCallback, useMemo, useRef, useState } from "react";
import Map, {
  Source,
  Layer,
  Popup,
  type MapRef,
  type ViewStateChangeEvent,
  type MapLayerMouseEvent,
} from "react-map-gl/maplibre";
import maplibregl from "maplibre-gl";
import { darkStyle } from "./styles/mapStyles";
import { useImperativeSource } from "@/hooks/useImperativeSource";
import {
  EMPTY_FC,
  buildSimulationActorsGeoJSON,
  buildSimulationRelationsGeoJSON,
} from "./geoJSONBuilders";

interface MaplibreViewerProps {
  shipsGeoJSON: GeoJSON.FeatureCollection<GeoJSON.Point>;
  simulationGeoJSON?: GeoJSON.FeatureCollection | null;
}

interface ActorPopupData {
  lng: number;
  lat: number;
  actor: string;
  stance: string;
  tension_level: number;
  key_statement: string;
  post_count: number;
  color: string;
}

const INITIAL_VIEW = {
  longitude: 115,
  latitude: 15,
  zoom: 4,
};

const EMPTY_GEOJSON: GeoJSON.FeatureCollection = {
  type: "FeatureCollection",
  features: [],
};

export default function MaplibreViewer({
  shipsGeoJSON,
  simulationGeoJSON,
}: MaplibreViewerProps) {
  const mapRef = useRef<MapRef>(null);
  const [popup, setPopup] = useState<ActorPopupData | null>(null);

  const actorsGeoJSON = useMemo(
    () => buildSimulationActorsGeoJSON(simulationGeoJSON) ?? EMPTY_GEOJSON,
    [simulationGeoJSON]
  );

  const relationsGeoJSON = useMemo(
    () => buildSimulationRelationsGeoJSON(simulationGeoJSON) ?? EMPTY_GEOJSON,
    [simulationGeoJSON]
  );

  useImperativeSource(mapRef.current, "ships", shipsGeoJSON);
  useImperativeSource(mapRef.current, "simulation-actors", actorsGeoJSON);
  useImperativeSource(mapRef.current, "simulation-relations", relationsGeoJSON);

  const onLoad = useCallback(() => {
    const map = mapRef.current;
    if (!map) return;

    const colors: Record<string, string> = {
      yellow: "#facc15",
      red: "#ef4444",
      blue: "#22d3ee",
    };

    for (const [name, color] of Object.entries(colors)) {
      const size = 24;
      const canvas = document.createElement("canvas");
      canvas.width = size;
      canvas.height = size;
      const ctx = canvas.getContext("2d");
      if (!ctx) continue;

      ctx.fillStyle = color;
      ctx.beginPath();
      ctx.moveTo(size / 2, 2);
      ctx.lineTo(size - 3, size - 2);
      ctx.lineTo(3, size - 2);
      ctx.closePath();
      ctx.fill();

      ctx.strokeStyle = "rgba(0,0,0,0.5)";
      ctx.lineWidth = 1;
      ctx.stroke();

      map.addImage(
        `ship-${name}`,
        {
          width: size,
          height: size,
          data: ctx.getImageData(0, 0, size, size).data,
        },
        { sdf: false }
      );
    }
  }, []);

  const onMove = useCallback((_evt: ViewStateChangeEvent) => {}, []);

  const onActorClick = useCallback((e: MapLayerMouseEvent) => {
    const feature = e.features?.[0];
    if (!feature || !feature.properties) return;

    const coords = (feature.geometry as GeoJSON.Point).coordinates;
    setPopup({
      lng: coords[0],
      lat: coords[1],
      actor: feature.properties.actor ?? "",
      stance: feature.properties.stance ?? "",
      tension_level: Number(feature.properties.tension_level) || 0,
      key_statement: feature.properties.key_statement ?? "",
      post_count: Number(feature.properties.post_count) || 0,
      color: feature.properties.color ?? "var(--accent-cyan)",
    });
  }, []);

  const stanceColor = (stance: string) => {
    const s = stance.toLowerCase();
    if (s.includes("hostile") || s.includes("aggressive")) return "#ef4444";
    if (s.includes("neutral")) return "#facc15";
    if (s.includes("friendly") || s.includes("cooperative")) return "#22c55e";
    return "#22d3ee";
  };

  return (
    <Map
      ref={mapRef}
      mapLib={maplibregl}
      initialViewState={INITIAL_VIEW}
      style={{ width: "100%", height: "100%" }}
      mapStyle={darkStyle}
      onLoad={onLoad}
      onMove={onMove}
      onClick={onActorClick}
      interactiveLayerIds={["simulation-actors-layer"]}
      attributionControl={false}
    >
      {/* Ships */}
      <Source
        id="ships"
        type="geojson"
        data={shipsGeoJSON ?? EMPTY_FC}
        cluster={true}
        clusterMaxZoom={4}
        clusterRadius={50}
      >
        <Layer
          id="ship-clusters"
          type="circle"
          filter={["has", "point_count"]}
          paint={{
            "circle-color": "#3b82f6",
            "circle-radius": [
              "step",
              ["get", "point_count"],
              15,
              10,
              20,
              50,
              25,
            ],
            "circle-opacity": 0.7,
            "circle-stroke-width": 1,
            "circle-stroke-color": "#60a5fa",
          }}
        />
        <Layer
          id="ship-cluster-count"
          type="symbol"
          filter={["has", "point_count"]}
          layout={{
            "text-field": "{point_count_abbreviated}",
            "text-size": 11,
          }}
          paint={{
            "text-color": "#ffffff",
          }}
        />
        <Layer
          id="ship-icons"
          type="symbol"
          filter={["!", ["has", "point_count"]]}
          layout={{
            "icon-image": ["concat", "ship-", ["get", "iconId"]],
            "icon-size": 0.8,
            "icon-rotate": ["get", "rotation"],
            "icon-rotation-alignment": "map",
            "icon-allow-overlap": true,
          }}
        />
      </Source>

      {/* Simulation Relations */}
      <Source id="simulation-relations" type="geojson" data={relationsGeoJSON}>
        <Layer
          id="simulation-relations-layer"
          type="line"
          paint={{
            "line-color": ["coalesce", ["get", "color"], "#22d3ee"],
            "line-width": [
              "interpolate",
              ["linear"],
              ["coalesce", ["get", "strength"], 0.5],
              0,
              1,
              0.5,
              2,
              1,
              4,
            ],
            "line-opacity": 0.6,
          }}
        />
      </Source>

      {/* Simulation Actors */}
      <Source id="simulation-actors" type="geojson" data={actorsGeoJSON}>
        <Layer
          id="simulation-actors-layer"
          type="circle"
          paint={{
            "circle-radius": [
              "interpolate",
              ["linear"],
              ["coalesce", ["get", "tension_level"], 0],
              0,
              8,
              0.5,
              14,
              1,
              22,
            ],
            "circle-color": ["coalesce", ["get", "color"], "#22d3ee"],
            "circle-opacity": 0.8,
            "circle-stroke-width": 2,
            "circle-stroke-color": "#ffffff",
          }}
        />
        <Layer
          id="simulation-actors-label"
          type="symbol"
          layout={{
            "text-field": ["get", "actor"],
            "text-size": 12,
            "text-offset": [0, 2],
            "text-anchor": "top",
          }}
          paint={{
            "text-color": "#ffffff",
            "text-halo-color": "#000000",
            "text-halo-width": 1,
          }}
        />
      </Source>

      {/* Actor Popup */}
      {popup && (
        <Popup
          longitude={popup.lng}
          latitude={popup.lat}
          onClose={() => setPopup(null)}
          closeButton={true}
          closeOnClick={false}
          anchor="bottom"
          offset={20}
          style={{ zIndex: 30 }}
        >
          <div
            style={{
              background: "rgb(12, 14, 18)",
              color: "#f3f4f6",
              padding: 12,
              borderRadius: 6,
              minWidth: 200,
              maxWidth: 280,
              fontSize: 12,
              lineHeight: 1.5,
            }}
          >
            <div
              style={{
                fontWeight: 700,
                fontSize: 14,
                marginBottom: 8,
                color: popup.color,
              }}
            >
              {popup.actor}
            </div>

            <div style={{ display: "flex", alignItems: "center", gap: 6, marginBottom: 6 }}>
              <span
                style={{
                  padding: "2px 8px",
                  borderRadius: 10,
                  fontSize: 10,
                  fontWeight: 600,
                  background: stanceColor(popup.stance),
                  color: "#000",
                  textTransform: "uppercase",
                }}
              >
                {popup.stance}
              </span>
              <span style={{ color: "rgb(107, 114, 128)", fontSize: 11 }}>
                posts: {popup.post_count}
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
                <span>{(popup.tension_level * 100).toFixed(0)}%</span>
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
                    width: `${popup.tension_level * 100}%`,
                    borderRadius: 2,
                    background:
                      popup.tension_level > 0.7
                        ? "#ef4444"
                        : popup.tension_level > 0.4
                          ? "#facc15"
                          : "#22c55e",
                  }}
                />
              </div>
            </div>

            {popup.key_statement && (
              <div
                style={{
                  marginTop: 8,
                  padding: "6px 8px",
                  background: "rgba(255,255,255,0.05)",
                  borderRadius: 4,
                  borderLeft: `3px solid ${popup.color}`,
                  fontSize: 11,
                  fontStyle: "italic",
                  color: "rgb(209, 213, 219)",
                }}
              >
                {popup.key_statement}
              </div>
            )}
          </div>
        </Popup>
      )}
    </Map>
  );
}
