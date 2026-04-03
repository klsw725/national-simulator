"use client";

import { memo, useCallback, useMemo, useRef, useState } from "react";
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
import renderPopupContent, { LAYER_TO_POPUP_TYPE } from "./MapPopupContent";
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
  uavsGeoJSON: GeoJSON.FeatureCollection<GeoJSON.Point>;
  trackedFlightsGeoJSON: GeoJSON.FeatureCollection<GeoJSON.Point>;
  cctvGeoJSON: GeoJSON.FeatureCollection<GeoJSON.Point>;
  kiwisdrGeoJSON: GeoJSON.FeatureCollection<GeoJSON.Point>;
  gpsJammingGeoJSON: GeoJSON.FeatureCollection<GeoJSON.Point>;
  earthquakesGeoJSON: GeoJSON.FeatureCollection<GeoJSON.Point>;
  firesGeoJSON: GeoJSON.FeatureCollection<GeoJSON.Point>;
  powerPlantsGeoJSON: GeoJSON.FeatureCollection<GeoJSON.Point>;
  datacentersGeoJSON: GeoJSON.FeatureCollection<GeoJSON.Point>;
  internetOutagesGeoJSON: GeoJSON.FeatureCollection<GeoJSON.Point>;
  wargamePhase?: string | null;
  onMapRef?: (ref: MapRef | null) => void;
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

function MaplibreViewer({
  shipsGeoJSON,
  militaryFlightsGeoJSON,
  satellitesGeoJSON,
  militaryBasesGeoJSON,
  simulationGeoJSON,
  layerVisibility,
  uavsGeoJSON,
  trackedFlightsGeoJSON,
  cctvGeoJSON,
  kiwisdrGeoJSON,
  gpsJammingGeoJSON,
  earthquakesGeoJSON,
  firesGeoJSON,
  powerPlantsGeoJSON,
  datacentersGeoJSON,
  internetOutagesGeoJSON,
  wargamePhase,
  onMapRef,
}: MaplibreViewerProps) {
  const mapRef = useRef<MapRef>(null);
  const [popup, setPopup] = useState<{
    type: string;
    lng: number;
    lat: number;
    properties: Record<string, unknown>;
  } | null>(null);

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
  useImperativeSource(mapRef.current, "uavs", uavsGeoJSON);
  useImperativeSource(mapRef.current, "tracked-flights", trackedFlightsGeoJSON);
  useImperativeSource(mapRef.current, "cctv", cctvGeoJSON);
  useImperativeSource(mapRef.current, "kiwisdr", kiwisdrGeoJSON);
  useImperativeSource(mapRef.current, "gps-jamming", gpsJammingGeoJSON);
  useImperativeSource(mapRef.current, "earthquakes", earthquakesGeoJSON);
  useImperativeSource(mapRef.current, "fires", firesGeoJSON);
  useImperativeSource(mapRef.current, "power-plants", powerPlantsGeoJSON);
  useImperativeSource(mapRef.current, "datacenters", datacentersGeoJSON);
  useImperativeSource(mapRef.current, "internet-outages", internetOutagesGeoJSON);

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
  }, []);

  const onMapClick = useCallback((e: MapLayerMouseEvent) => {
    const feature = e.features?.[0];
    if (!feature || !feature.properties) {
      setPopup(null);
      return;
    }

    const layerId = feature.layer?.id;
    if (!layerId) return;

    const popupType = LAYER_TO_POPUP_TYPE[layerId];
    if (!popupType) return;

    const coords = (feature.geometry as GeoJSON.Point).coordinates;
    setPopup({
      type: popupType,
      lng: coords[0],
      lat: coords[1],
      properties: feature.properties as Record<string, unknown>,
    });
  }, []);

  return (
    <Map
      ref={(ref) => {
        (mapRef as React.MutableRefObject<MapRef | null>).current = ref;
        onMapRef?.(ref);
      }}
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
        "uavs-layer",
        "tracked-flights-layer",
        "kiwisdr-layer",
        "gps-jamming-layer",
        "earthquakes-layer",
        "power-plants-layer",
        "datacenters-layer",
        "internet-outages-layer",
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
        cluster={true}
        clusterMaxZoom={5}
        clusterRadius={40}
      >
        <Layer
          id="military-flights-cluster"
          type="circle"
          filter={["has", "point_count"]}
          layout={{ visibility: layerVisibility.militaryFlights ? "visible" : "none" }}
          paint={{
            "circle-color": "#f97316",
            "circle-radius": ["step", ["get", "point_count"], 15, 10, 20, 50, 25],
            "circle-opacity": 0.7,
          }}
        />
        <Layer
          id="military-flights-cluster-count"
          type="symbol"
          filter={["has", "point_count"]}
          layout={{
            "text-field": ["get", "point_count_abbreviated"],
            "text-font": ["Open Sans Regular"],
            "text-size": 10,
            visibility: layerVisibility.militaryFlights ? "visible" : "none",
          }}
          paint={{ "text-color": "#ffffff" }}
        />
        <Layer
          id="military-flights-layer"
          type="circle"
          filter={["!", ["has", "point_count"]]}
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
          minzoom={6}
          filter={["!", ["has", "point_count"]]}
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
        cluster={true}
        clusterMaxZoom={4}
        clusterRadius={50}
      >
        <Layer
          id="satellites-cluster"
          type="circle"
          filter={["has", "point_count"]}
          layout={{ visibility: layerVisibility.satellites ? "visible" : "none" }}
          paint={{
            "circle-color": "#a855f7",
            "circle-radius": ["step", ["get", "point_count"], 15, 10, 20, 50, 25],
            "circle-opacity": 0.7,
          }}
        />
        <Layer
          id="satellites-cluster-count"
          type="symbol"
          filter={["has", "point_count"]}
          layout={{
            "text-field": ["get", "point_count_abbreviated"],
            "text-font": ["Open Sans Regular"],
            "text-size": 10,
            visibility: layerVisibility.satellites ? "visible" : "none",
          }}
          paint={{ "text-color": "#ffffff" }}
        />
        <Layer
          id="satellites-layer"
          type="circle"
          filter={["!", ["has", "point_count"]]}
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
          minzoom={6}
          filter={["!", ["has", "point_count"]]}
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
        cluster={true}
        clusterMaxZoom={6}
        clusterRadius={30}
      >
        <Layer
          id="military-bases-cluster"
          type="circle"
          filter={["has", "point_count"]}
          layout={{ visibility: layerVisibility.militaryBases ? "visible" : "none" }}
          paint={{
            "circle-color": "#ef4444",
            "circle-radius": ["step", ["get", "point_count"], 15, 10, 20, 50, 25],
            "circle-opacity": 0.7,
          }}
        />
        <Layer
          id="military-bases-cluster-count"
          type="symbol"
          filter={["has", "point_count"]}
          layout={{
            "text-field": ["get", "point_count_abbreviated"],
            "text-font": ["Open Sans Regular"],
            "text-size": 10,
            visibility: layerVisibility.militaryBases ? "visible" : "none",
          }}
          paint={{ "text-color": "#ffffff" }}
        />
        <Layer
          id="military-bases-layer"
          type="circle"
          filter={["!", ["has", "point_count"]]}
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
          minzoom={6}
          filter={["!", ["has", "point_count"]]}
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

      {/* UAVs */}
      <Source
        id="uavs"
        type="geojson"
        data={uavsGeoJSON ?? EMPTY_FC}
      >
        <Layer
          id="uavs-layer"
          type="circle"
          layout={{ visibility: layerVisibility.uavs ? "visible" : "none" }}
          paint={{
            "circle-radius": 6,
            "circle-color": "#eab308",
            "circle-opacity": 0.9,
            "circle-stroke-width": 1,
            "circle-stroke-color": "rgba(234,179,8,0.4)",
          }}
        />
        <Layer
          id="uavs-label"
          type="symbol"
          minzoom={6}
          layout={{
            "text-field": ["get", "callsign"],
            "text-font": ["Open Sans Regular"],
            "text-size": 10,
            "text-offset": [0, 1.3],
            "text-anchor": "top",
            visibility: layerVisibility.uavs ? "visible" : "none",
          }}
          paint={{
            "text-color": "#eab308",
            "text-halo-color": "#000000",
            "text-halo-width": 1,
          }}
        />
      </Source>

      {/* Tracked Flights */}
      <Source
        id="tracked-flights"
        type="geojson"
        data={trackedFlightsGeoJSON ?? EMPTY_FC}
      >
        <Layer
          id="tracked-flights-layer"
          type="circle"
          layout={{ visibility: layerVisibility.trackedFlights ? "visible" : "none" }}
          paint={{
            "circle-radius": 6,
            "circle-color": "#ec4899",
            "circle-opacity": 0.9,
            "circle-stroke-width": 1,
            "circle-stroke-color": "rgba(236,72,153,0.4)",
          }}
        />
        <Layer
          id="tracked-flights-label"
          type="symbol"
          minzoom={6}
          layout={{
            "text-field": ["get", "callsign"],
            "text-font": ["Open Sans Regular"],
            "text-size": 10,
            "text-offset": [0, 1.3],
            "text-anchor": "top",
            visibility: layerVisibility.trackedFlights ? "visible" : "none",
          }}
          paint={{
            "text-color": "#ec4899",
            "text-halo-color": "#000000",
            "text-halo-width": 1,
          }}
        />
      </Source>

      {/* CCTV */}
      <Source
        id="cctv"
        type="geojson"
        data={cctvGeoJSON ?? EMPTY_FC}
      >
        <Layer
          id="cctv-layer"
          type="circle"
          layout={{ visibility: layerVisibility.cctv ? "visible" : "none" }}
          paint={{
            "circle-radius": 3,
            "circle-color": "#78716c",
            "circle-opacity": 0.8,
            "circle-stroke-width": 1,
            "circle-stroke-color": "rgba(120,113,108,0.4)",
          }}
        />
      </Source>

      {/* KiwiSDR */}
      <Source
        id="kiwisdr"
        type="geojson"
        data={kiwisdrGeoJSON ?? EMPTY_FC}
      >
        <Layer
          id="kiwisdr-layer"
          type="circle"
          layout={{ visibility: layerVisibility.kiwisdr ? "visible" : "none" }}
          paint={{
            "circle-radius": 5,
            "circle-color": "#14b8a6",
            "circle-opacity": 0.9,
            "circle-stroke-width": 1,
            "circle-stroke-color": "rgba(20,184,166,0.4)",
          }}
        />
        <Layer
          id="kiwisdr-label"
          type="symbol"
          minzoom={6}
          layout={{
            "text-field": ["get", "location_name"],
            "text-font": ["Open Sans Regular"],
            "text-size": 10,
            "text-offset": [0, 1.3],
            "text-anchor": "top",
            visibility: layerVisibility.kiwisdr ? "visible" : "none",
          }}
          paint={{
            "text-color": "#14b8a6",
            "text-halo-color": "#000000",
            "text-halo-width": 1,
          }}
        />
      </Source>

      {/* GPS Jamming */}
      <Source
        id="gps-jamming"
        type="geojson"
        data={gpsJammingGeoJSON ?? EMPTY_FC}
      >
        <Layer
          id="gps-jamming-layer"
          type="circle"
          layout={{ visibility: layerVisibility.gpsJamming ? "visible" : "none" }}
          paint={{
            "circle-radius": [
              "interpolate",
              ["linear"],
              ["get", "severity"],
              0,
              6,
              100,
              16,
            ],
            "circle-color": "#dc2626",
            "circle-opacity": 0.6,
            "circle-stroke-width": 2,
            "circle-stroke-color": "rgba(220,38,38,0.4)",
          }}
        />
      </Source>

      {/* Earthquakes */}
      <Source
        id="earthquakes"
        type="geojson"
        data={earthquakesGeoJSON ?? EMPTY_FC}
      >
        <Layer
          id="earthquakes-layer"
          type="circle"
          layout={{ visibility: layerVisibility.earthquakes ? "visible" : "none" }}
          paint={{
            "circle-radius": [
              "interpolate",
              ["linear"],
              ["get", "mag"],
              3,
              5,
              7,
              18,
            ],
            "circle-color": "#b91c1c",
            "circle-opacity": 0.85,
            "circle-stroke-width": 1,
            "circle-stroke-color": "rgba(185,28,28,0.4)",
          }}
        />
        <Layer
          id="earthquakes-label"
          type="symbol"
          minzoom={6}
          layout={{
            "text-field": ["get", "place"],
            "text-font": ["Open Sans Regular"],
            "text-size": 10,
            "text-offset": [0, 1.3],
            "text-anchor": "top",
            visibility: layerVisibility.earthquakes ? "visible" : "none",
          }}
          paint={{
            "text-color": "#b91c1c",
            "text-halo-color": "#000000",
            "text-halo-width": 1,
          }}
        />
      </Source>

      {/* Fires */}
      <Source
        id="fires"
        type="geojson"
        data={firesGeoJSON ?? EMPTY_FC}
      >
        <Layer
          id="fires-layer"
          type="circle"
          layout={{ visibility: layerVisibility.firmsFires ? "visible" : "none" }}
          paint={{
            "circle-radius": 3,
            "circle-color": "#ea580c",
            "circle-opacity": 0.7,
            "circle-stroke-width": 1,
            "circle-stroke-color": "rgba(234,88,12,0.3)",
          }}
        />
      </Source>

      {/* Power Plants */}
      <Source
        id="power-plants"
        type="geojson"
        data={powerPlantsGeoJSON ?? EMPTY_FC}
      >
        <Layer
          id="power-plants-layer"
          type="circle"
          layout={{ visibility: layerVisibility.powerPlants ? "visible" : "none" }}
          paint={{
            "circle-radius": 6,
            "circle-color": "#f59e0b",
            "circle-opacity": 0.9,
            "circle-stroke-width": 1,
            "circle-stroke-color": "rgba(245,158,11,0.4)",
          }}
        />
        <Layer
          id="power-plants-label"
          type="symbol"
          minzoom={6}
          layout={{
            "text-field": ["get", "name"],
            "text-font": ["Open Sans Regular"],
            "text-size": 10,
            "text-offset": [0, 1.3],
            "text-anchor": "top",
            visibility: layerVisibility.powerPlants ? "visible" : "none",
          }}
          paint={{
            "text-color": "#f59e0b",
            "text-halo-color": "#000000",
            "text-halo-width": 1,
          }}
        />
      </Source>

      {/* Datacenters */}
      <Source
        id="datacenters"
        type="geojson"
        data={datacentersGeoJSON ?? EMPTY_FC}
      >
        <Layer
          id="datacenters-layer"
          type="circle"
          layout={{ visibility: layerVisibility.datacenters ? "visible" : "none" }}
          paint={{
            "circle-radius": 5,
            "circle-color": "#6366f1",
            "circle-opacity": 0.9,
            "circle-stroke-width": 2,
            "circle-stroke-color": "rgba(99,102,241,0.5)",
          }}
        />
        <Layer
          id="datacenters-label"
          type="symbol"
          minzoom={6}
          layout={{
            "text-field": ["get", "name"],
            "text-font": ["Open Sans Regular"],
            "text-size": 10,
            "text-offset": [0, 1.3],
            "text-anchor": "top",
            visibility: layerVisibility.datacenters ? "visible" : "none",
          }}
          paint={{
            "text-color": "#6366f1",
            "text-halo-color": "#000000",
            "text-halo-width": 1,
          }}
        />
      </Source>

      {/* Internet Outages */}
      <Source
        id="internet-outages"
        type="geojson"
        data={internetOutagesGeoJSON ?? EMPTY_FC}
      >
        <Layer
          id="internet-outages-layer"
          type="circle"
          layout={{ visibility: layerVisibility.internetOutages ? "visible" : "none" }}
          paint={{
            "circle-radius": [
              "interpolate",
              ["linear"],
              ["get", "severity"],
              0,
              5,
              100,
              14,
            ],
            "circle-color": "#7c3aed",
            "circle-opacity": 0.85,
            "circle-stroke-width": 1,
            "circle-stroke-color": "rgba(124,58,237,0.4)",
          }}
        />
        <Layer
          id="internet-outages-label"
          type="symbol"
          minzoom={6}
          layout={{
            "text-field": ["get", "region_name"],
            "text-font": ["Open Sans Regular"],
            "text-size": 10,
            "text-offset": [0, 1.3],
            "text-anchor": "top",
            visibility: layerVisibility.internetOutages ? "visible" : "none",
          }}
          paint={{
            "text-color": "#7c3aed",
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
            "line-color": wargamePhase === "briefing"
              ? "#60a5fa"
              : wargamePhase === "decision"
                ? "#f59e0b"
                : ["coalesce", ["get", "color"], "#22d3ee"],
            "line-width": [
              "interpolate",
              ["linear"],
              ["coalesce", ["get", "strength"], 0.5],
              0,
              wargamePhase ? 2 : 1,
              0.5,
              wargamePhase ? 3 : 2,
              1,
              wargamePhase ? 5 : 4,
            ],
            "line-opacity": wargamePhase ? 0.8 : 0.6,
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
              wargamePhase === "decision" ? 12 : 8,
              0.5,
              wargamePhase === "decision" ? 18 : 14,
              1,
              wargamePhase === "decision" ? 28 : 22,
            ],
            "circle-color": wargamePhase === "decision"
              ? "#f59e0b"
              : wargamePhase === "briefing"
                ? "#60a5fa"
                : ["coalesce", ["get", "color"], "#22d3ee"],
            "circle-opacity": wargamePhase === "decision" || wargamePhase === "briefing" ? 0.9 : 0.8,
            "circle-stroke-width": wargamePhase === "decision" ? 3 : 2,
            "circle-stroke-color": wargamePhase === "decision"
              ? "#fbbf24"
              : "#ffffff",
          }}
        />
        <Layer
          id="simulation-actors-label"
          type="symbol"
          minzoom={6}
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
              minWidth: popup.type === "actor" ? 200 : 180,
              maxWidth: popup.type === "actor" ? 280 : 260,
              fontSize: 12,
              lineHeight: 1.5,
            }}
          >
            {renderPopupContent(popup.type, popup.properties)}
          </div>
        </Popup>
      )}
    </Map>
  );
}

export default memo(MaplibreViewer);
