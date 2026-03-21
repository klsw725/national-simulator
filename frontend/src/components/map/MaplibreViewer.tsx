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
import type { LayerVisibility } from "./LayerToggle";

interface MaplibreViewerProps {
  shipsGeoJSON: GeoJSON.FeatureCollection<GeoJSON.Point>;
  militaryFlightsGeoJSON: GeoJSON.FeatureCollection<GeoJSON.Point>;
  satellitesGeoJSON: GeoJSON.FeatureCollection<GeoJSON.Point>;
  militaryBasesGeoJSON: GeoJSON.FeatureCollection<GeoJSON.Point>;
  simulationGeoJSON?: GeoJSON.FeatureCollection | null;
  layerVisibility: LayerVisibility;
}

interface ShipPopupData {
  lng: number;
  lat: number;
  name: string;
  type: string;
  mmsi: string;
  sog: number;
  country: string;
}

interface FlightPopupData {
  lng: number;
  lat: number;
  callsign: string;
  country: string;
  force: string;
  military_type: string;
  model: string;
  alt: number;
  speed_knots: number;
}

interface SatellitePopupData {
  lng: number;
  lat: number;
  name: string;
  country: string;
  mission: string;
  sat_type: string;
  alt_km: number;
}

interface BasePopupData {
  lng: number;
  lat: number;
  name: string;
  country: string;
  branch: string;
  operator: string;
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
  militaryFlightsGeoJSON,
  satellitesGeoJSON,
  militaryBasesGeoJSON,
  simulationGeoJSON,
  layerVisibility,
}: MaplibreViewerProps) {
  const mapRef = useRef<MapRef>(null);
  const [popup, setPopup] = useState<ActorPopupData | null>(null);
  const [shipPopup, setShipPopup] = useState<ShipPopupData | null>(null);
  const [flightPopup, setFlightPopup] = useState<FlightPopupData | null>(null);
  const [satPopup, setSatPopup] = useState<SatellitePopupData | null>(null);
  const [basePopup, setBasePopup] = useState<BasePopupData | null>(null);

  const actorsGeoJSON = useMemo(
    () => buildSimulationActorsGeoJSON(simulationGeoJSON) ?? EMPTY_GEOJSON,
    [simulationGeoJSON]
  );

  const relationsGeoJSON = useMemo(
    () => buildSimulationRelationsGeoJSON(simulationGeoJSON) ?? EMPTY_GEOJSON,
    [simulationGeoJSON]
  );

  useImperativeSource(mapRef.current, "ships", shipsGeoJSON);
  useImperativeSource(mapRef.current, "military-flights", militaryFlightsGeoJSON);
  useImperativeSource(mapRef.current, "satellites", satellitesGeoJSON);
  useImperativeSource(mapRef.current, "military-bases", militaryBasesGeoJSON);
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

  const clearPopups = useCallback(() => {
    setPopup(null);
    setShipPopup(null);
    setFlightPopup(null);
    setSatPopup(null);
    setBasePopup(null);
  }, []);

  const onMapClick = useCallback((e: MapLayerMouseEvent) => {
    const feature = e.features?.[0];
    if (!feature || !feature.properties) return;

    const layerId = feature.layer?.id;
    const coords = (feature.geometry as GeoJSON.Point).coordinates;
    clearPopups();

    if (layerId === "ship-icons") {
      setShipPopup({
        lng: coords[0],
        lat: coords[1],
        name: feature.properties.name ?? "Unknown",
        type: feature.properties.type ?? "unknown",
        mmsi: feature.properties.id ?? "",
        sog: Number(feature.properties.sog) || 0,
        country: feature.properties.country ?? "",
      });
    } else if (layerId === "military-flights-layer") {
      setFlightPopup({
        lng: coords[0],
        lat: coords[1],
        callsign: feature.properties.callsign ?? "",
        country: feature.properties.country ?? "",
        force: feature.properties.force ?? "",
        military_type: feature.properties.military_type ?? "",
        model: feature.properties.model ?? "",
        alt: Number(feature.properties.alt) || 0,
        speed_knots: Number(feature.properties.speed_knots) || 0,
      });
    } else if (layerId === "satellites-layer") {
      setSatPopup({
        lng: coords[0],
        lat: coords[1],
        name: feature.properties.name ?? "",
        country: feature.properties.country ?? "",
        mission: feature.properties.mission ?? "",
        sat_type: feature.properties.sat_type ?? "",
        alt_km: Number(feature.properties.alt_km) || 0,
      });
    } else if (layerId === "military-bases-layer") {
      setBasePopup({
        lng: coords[0],
        lat: coords[1],
        name: feature.properties.name ?? "",
        country: feature.properties.country ?? "",
        branch: feature.properties.branch ?? "",
        operator: feature.properties.operator ?? "",
      });
    } else if (layerId === "simulation-actors-layer") {
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
    }
  }, [clearPopups]);

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
      onClick={onMapClick}
      interactiveLayerIds={[
        "ship-icons",
        "military-flights-layer",
        "satellites-layer",
        "military-bases-layer",
        "simulation-actors-layer",
      ]}
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
          layout={{ visibility: layerVisibility.ships ? "visible" : "none" }}
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
            "text-font": ["Open Sans Regular"],
            "text-size": 11,
            visibility: layerVisibility.ships ? "visible" : "none",
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
            visibility: layerVisibility.ships ? "visible" : "none",
          }}
        />
      </Source>

      {/* Military Flights */}
      <Source
        id="military-flights"
        type="geojson"
        data={militaryFlightsGeoJSON ?? EMPTY_FC}
      >
        <Layer
          id="military-flights-layer"
          type="circle"
          layout={{ visibility: layerVisibility.militaryFlights ? "visible" : "none" }}
          paint={{
            "circle-radius": 5,
            "circle-color": "#f97316",
            "circle-opacity": 0.9,
            "circle-stroke-width": 1,
            "circle-stroke-color": "rgba(249,115,22,0.4)",
          }}
        />
        <Layer
          id="military-flights-label"
          type="symbol"
          layout={{
            "text-field": ["get", "callsign"],
            "text-font": ["Open Sans Regular"],
            "text-size": 10,
            "text-offset": [0, 1.4],
            "text-anchor": "top",
            visibility: layerVisibility.militaryFlights ? "visible" : "none",
          }}
          paint={{
            "text-color": "#f97316",
            "text-halo-color": "#000000",
            "text-halo-width": 1,
          }}
        />
      </Source>

      {/* Satellites */}
      <Source
        id="satellites"
        type="geojson"
        data={satellitesGeoJSON ?? EMPTY_FC}
      >
        <Layer
          id="satellites-layer"
          type="circle"
          layout={{ visibility: layerVisibility.satellites ? "visible" : "none" }}
          paint={{
            "circle-radius": 4,
            "circle-color": "#a855f7",
            "circle-opacity": 0.85,
            "circle-stroke-width": 1,
            "circle-stroke-color": "rgba(168,85,247,0.4)",
          }}
        />
        <Layer
           id="satellites-label"
          type="symbol"
          layout={{
            "text-field": ["get", "name"],
            "text-font": ["Open Sans Regular"],
            "text-size": 10,
            "text-offset": [0, 1.3],
            "text-anchor": "top",
            visibility: layerVisibility.satellites ? "visible" : "none",
          }}
          paint={{
            "text-color": "#a855f7",
            "text-halo-color": "#000000",
            "text-halo-width": 1,
          }}
        />
      </Source>

      {/* Military Bases */}
      <Source
        id="military-bases"
        type="geojson"
        data={militaryBasesGeoJSON ?? EMPTY_FC}
      >
        <Layer
          id="military-bases-layer"
          type="circle"
          layout={{ visibility: layerVisibility.militaryBases ? "visible" : "none" }}
          paint={{
            "circle-radius": 7,
            "circle-color": "#ef4444",
            "circle-opacity": 0.8,
            "circle-stroke-width": 2,
            "circle-stroke-color": "rgba(239,68,68,0.3)",
          }}
        />
        <Layer
           id="military-bases-label"
          type="symbol"
          layout={{
            "text-field": ["get", "name"],
            "text-font": ["Open Sans Regular"],
            "text-size": 10,
            "text-offset": [0, 1.5],
            "text-anchor": "top",
            visibility: layerVisibility.militaryBases ? "visible" : "none",
          }}
          paint={{
            "text-color": "#ef4444",
            "text-halo-color": "#000000",
            "text-halo-width": 1,
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
            "text-font": ["Open Sans Regular"],
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

      {shipPopup && (
        <Popup
          longitude={shipPopup.lng}
          latitude={shipPopup.lat}
          onClose={() => setShipPopup(null)}
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
              minWidth: 180,
              maxWidth: 260,
              fontSize: 12,
              lineHeight: 1.5,
            }}
          >
            <div
              style={{
                fontWeight: 700,
                fontSize: 14,
                marginBottom: 6,
                color: "#22d3ee",
              }}
            >
              {shipPopup.name}
            </div>
            <div style={{ display: "flex", alignItems: "center", gap: 6, marginBottom: 8 }}>
              <span
                style={{
                  padding: "2px 8px",
                  borderRadius: 10,
                  fontSize: 10,
                  fontWeight: 600,
                  background: shipPopup.type === "military_vessel" ? "#facc15" : "#3b82f6",
                  color: "#000",
                  textTransform: "uppercase",
                }}
              >
                {shipPopup.type.replace(/_/g, " ")}
              </span>
            </div>
            <div style={{ display: "flex", flexDirection: "column", gap: 3, fontSize: 11 }}>
              <div style={{ display: "flex", justifyContent: "space-between" }}>
                <span style={{ color: "rgb(107, 114, 128)" }}>MMSI</span>
                <span>{shipPopup.mmsi}</span>
              </div>
              <div style={{ display: "flex", justifyContent: "space-between" }}>
                <span style={{ color: "rgb(107, 114, 128)" }}>SOG</span>
                <span>{shipPopup.sog.toFixed(1)} kn</span>
              </div>
              <div style={{ display: "flex", justifyContent: "space-between" }}>
                <span style={{ color: "rgb(107, 114, 128)" }}>Country</span>
                <span>{shipPopup.country || "Unknown"}</span>
              </div>
            </div>
          </div>
        </Popup>
      )}

      {flightPopup && (
        <Popup
          longitude={flightPopup.lng}
          latitude={flightPopup.lat}
          onClose={() => setFlightPopup(null)}
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
              minWidth: 180,
              maxWidth: 260,
              fontSize: 12,
              lineHeight: 1.5,
            }}
          >
            <div
              style={{
                fontWeight: 700,
                fontSize: 14,
                marginBottom: 6,
                color: "#f97316",
              }}
            >
              {flightPopup.callsign}
            </div>
            {flightPopup.force && (
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
                  {flightPopup.force}
                </span>
                {flightPopup.military_type && (
                  <span style={{ color: "rgb(107, 114, 128)", fontSize: 11 }}>
                    {flightPopup.military_type}
                  </span>
                )}
              </div>
            )}
            <div style={{ display: "flex", flexDirection: "column", gap: 3, fontSize: 11 }}>
              <div style={{ display: "flex", justifyContent: "space-between" }}>
                <span style={{ color: "rgb(107, 114, 128)" }}>Model</span>
                <span>{flightPopup.model || "Unknown"}</span>
              </div>
              <div style={{ display: "flex", justifyContent: "space-between" }}>
                <span style={{ color: "rgb(107, 114, 128)" }}>Altitude</span>
                <span>{flightPopup.alt.toLocaleString()} ft</span>
              </div>
              <div style={{ display: "flex", justifyContent: "space-between" }}>
                <span style={{ color: "rgb(107, 114, 128)" }}>Speed</span>
                <span>{flightPopup.speed_knots.toFixed(0)} kn</span>
              </div>
              <div style={{ display: "flex", justifyContent: "space-between" }}>
                <span style={{ color: "rgb(107, 114, 128)" }}>Country</span>
                <span>{flightPopup.country || "Unknown"}</span>
              </div>
            </div>
          </div>
        </Popup>
      )}

      {satPopup && (
        <Popup
          longitude={satPopup.lng}
          latitude={satPopup.lat}
          onClose={() => setSatPopup(null)}
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
              minWidth: 180,
              maxWidth: 260,
              fontSize: 12,
              lineHeight: 1.5,
            }}
          >
            <div
              style={{
                fontWeight: 700,
                fontSize: 14,
                marginBottom: 6,
                color: "#a855f7",
              }}
            >
              {satPopup.name}
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
                {satPopup.sat_type}
              </span>
            </div>
            <div style={{ display: "flex", flexDirection: "column", gap: 3, fontSize: 11 }}>
              <div style={{ display: "flex", justifyContent: "space-between" }}>
                <span style={{ color: "rgb(107, 114, 128)" }}>Mission</span>
                <span>{satPopup.mission || "Unknown"}</span>
              </div>
              <div style={{ display: "flex", justifyContent: "space-between" }}>
                <span style={{ color: "rgb(107, 114, 128)" }}>Altitude</span>
                <span>{satPopup.alt_km.toLocaleString()} km</span>
              </div>
              <div style={{ display: "flex", justifyContent: "space-between" }}>
                <span style={{ color: "rgb(107, 114, 128)" }}>Country</span>
                <span>{satPopup.country || "Unknown"}</span>
              </div>
            </div>
          </div>
        </Popup>
      )}

      {basePopup && (
        <Popup
          longitude={basePopup.lng}
          latitude={basePopup.lat}
          onClose={() => setBasePopup(null)}
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
              minWidth: 180,
              maxWidth: 260,
              fontSize: 12,
              lineHeight: 1.5,
            }}
          >
            <div
              style={{
                fontWeight: 700,
                fontSize: 14,
                marginBottom: 6,
                color: "#ef4444",
              }}
            >
              {basePopup.name}
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
                {basePopup.branch}
              </span>
            </div>
            <div style={{ display: "flex", flexDirection: "column", gap: 3, fontSize: 11 }}>
              <div style={{ display: "flex", justifyContent: "space-between" }}>
                <span style={{ color: "rgb(107, 114, 128)" }}>Operator</span>
                <span>{basePopup.operator || "Unknown"}</span>
              </div>
              <div style={{ display: "flex", justifyContent: "space-between" }}>
                <span style={{ color: "rgb(107, 114, 128)" }}>Country</span>
                <span>{basePopup.country || "Unknown"}</span>
              </div>
            </div>
          </div>
        </Popup>
      )}
    </Map>
  );
}
