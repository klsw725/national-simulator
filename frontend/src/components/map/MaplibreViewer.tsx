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

interface UavPopupData {
  lng: number;
  lat: number;
  callsign: string;
  country: string;
  alt: number;
  speed_knots: number;
  model: string;
}

interface TrackedFlightPopupData {
  lng: number;
  lat: number;
  callsign: string;
  country: string;
  alt: number;
  speed_knots: number;
  model: string;
  airline: string;
}

interface KiwisdrPopupData {
  lng: number;
  lat: number;
  location_name: string;
  frequency: string;
  band: string;
  url: string;
}

interface GpsJammingPopupData {
  lng: number;
  lat: number;
  severity: number;
  source: string;
  region: string;
  affected_area_km: number;
}

interface EarthquakePopupData {
  lng: number;
  lat: number;
  place: string;
  mag: number;
  depth_km: number;
  time: string;
}

interface PowerPlantPopupData {
  lng: number;
  lat: number;
  name: string;
  fuel_type: string;
  capacity_mw: number;
  country: string;
}

interface DatacenterPopupData {
  lng: number;
  lat: number;
  name: string;
  operator: string;
  country: string;
}

interface InternetOutagePopupData {
  lng: number;
  lat: number;
  region_name: string;
  severity: number;
  provider: string;
  affected_users: number;
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
}: MaplibreViewerProps) {
  const mapRef = useRef<MapRef>(null);
  const [popup, setPopup] = useState<ActorPopupData | null>(null);
  const [shipPopup, setShipPopup] = useState<ShipPopupData | null>(null);
  const [flightPopup, setFlightPopup] = useState<FlightPopupData | null>(null);
  const [satPopup, setSatPopup] = useState<SatellitePopupData | null>(null);
  const [basePopup, setBasePopup] = useState<BasePopupData | null>(null);
  const [uavPopup, setUavPopup] = useState<UavPopupData | null>(null);
  const [trackedFlightPopup, setTrackedFlightPopup] = useState<TrackedFlightPopupData | null>(null);
  const [kiwisdrPopup, setKiwisdrPopup] = useState<KiwisdrPopupData | null>(null);
  const [gpsJammingPopup, setGpsJammingPopup] = useState<GpsJammingPopupData | null>(null);
  const [earthquakePopup, setEarthquakePopup] = useState<EarthquakePopupData | null>(null);
  const [powerPlantPopup, setPowerPlantPopup] = useState<PowerPlantPopupData | null>(null);
  const [datacenterPopup, setDatacenterPopup] = useState<DatacenterPopupData | null>(null);
  const [internetOutagePopup, setInternetOutagePopup] = useState<InternetOutagePopupData | null>(null);

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
    setShipPopup(null);
    setFlightPopup(null);
    setSatPopup(null);
    setBasePopup(null);
    setUavPopup(null);
    setTrackedFlightPopup(null);
    setKiwisdrPopup(null);
    setGpsJammingPopup(null);
    setEarthquakePopup(null);
    setPowerPlantPopup(null);
    setDatacenterPopup(null);
    setInternetOutagePopup(null);
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
    } else if (layerId === "uavs-layer") {
      setUavPopup({
        lng: coords[0],
        lat: coords[1],
        callsign: feature.properties.callsign ?? "",
        country: feature.properties.country ?? "",
        alt: Number(feature.properties.alt) || 0,
        speed_knots: Number(feature.properties.speed_knots) || 0,
        model: feature.properties.model ?? "",
      });
    } else if (layerId === "tracked-flights-layer") {
      setTrackedFlightPopup({
        lng: coords[0],
        lat: coords[1],
        callsign: feature.properties.callsign ?? "",
        country: feature.properties.country ?? "",
        alt: Number(feature.properties.alt) || 0,
        speed_knots: Number(feature.properties.speed_knots) || 0,
        model: feature.properties.model ?? "",
        airline: feature.properties.airline ?? "",
      });
    } else if (layerId === "kiwisdr-layer") {
      setKiwisdrPopup({
        lng: coords[0],
        lat: coords[1],
        location_name: feature.properties.location_name ?? "",
        frequency: feature.properties.frequency ?? "",
        band: feature.properties.band ?? "",
        url: feature.properties.url ?? "",
      });
    } else if (layerId === "gps-jamming-layer") {
      setGpsJammingPopup({
        lng: coords[0],
        lat: coords[1],
        severity: Number(feature.properties.severity) || 0,
        source: feature.properties.source ?? "",
        region: feature.properties.region ?? "",
        affected_area_km: Number(feature.properties.affected_area_km) || 0,
      });
    } else if (layerId === "earthquakes-layer") {
      setEarthquakePopup({
        lng: coords[0],
        lat: coords[1],
        place: feature.properties.place ?? "",
        mag: Number(feature.properties.mag) || 0,
        depth_km: Number(feature.properties.depth_km) || 0,
        time: feature.properties.time ?? "",
      });
    } else if (layerId === "power-plants-layer") {
      setPowerPlantPopup({
        lng: coords[0],
        lat: coords[1],
        name: feature.properties.name ?? "",
        fuel_type: feature.properties.fuel_type ?? "",
        capacity_mw: Number(feature.properties.capacity_mw) || 0,
        country: feature.properties.country ?? "",
      });
    } else if (layerId === "datacenters-layer") {
      setDatacenterPopup({
        lng: coords[0],
        lat: coords[1],
        name: feature.properties.name ?? "",
        operator: feature.properties.operator ?? "",
        country: feature.properties.country ?? "",
      });
    } else if (layerId === "internet-outages-layer") {
      setInternetOutagePopup({
        lng: coords[0],
        lat: coords[1],
        region_name: feature.properties.region_name ?? "",
        severity: Number(feature.properties.severity) || 0,
        provider: feature.properties.provider ?? "",
        affected_users: Number(feature.properties.affected_users) || 0,
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

      {uavPopup && (
        <Popup
          longitude={uavPopup.lng}
          latitude={uavPopup.lat}
          onClose={() => setUavPopup(null)}
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
                color: "#eab308",
              }}
            >
              {uavPopup.callsign}
            </div>
            <div style={{ display: "flex", flexDirection: "column", gap: 3, fontSize: 11 }}>
              <div style={{ display: "flex", justifyContent: "space-between" }}>
                <span style={{ color: "rgb(107, 114, 128)" }}>Model</span>
                <span>{uavPopup.model || "Unknown"}</span>
              </div>
              <div style={{ display: "flex", justifyContent: "space-between" }}>
                <span style={{ color: "rgb(107, 114, 128)" }}>Altitude</span>
                <span>{uavPopup.alt.toLocaleString()} ft</span>
              </div>
              <div style={{ display: "flex", justifyContent: "space-between" }}>
                <span style={{ color: "rgb(107, 114, 128)" }}>Speed</span>
                <span>{uavPopup.speed_knots.toFixed(0)} kn</span>
              </div>
              <div style={{ display: "flex", justifyContent: "space-between" }}>
                <span style={{ color: "rgb(107, 114, 128)" }}>Country</span>
                <span>{uavPopup.country || "Unknown"}</span>
              </div>
            </div>
          </div>
        </Popup>
      )}

      {trackedFlightPopup && (
        <Popup
          longitude={trackedFlightPopup.lng}
          latitude={trackedFlightPopup.lat}
          onClose={() => setTrackedFlightPopup(null)}
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
                color: "#ec4899",
              }}
            >
              {trackedFlightPopup.callsign}
            </div>
            {trackedFlightPopup.airline && (
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
                  {trackedFlightPopup.airline}
                </span>
              </div>
            )}
            <div style={{ display: "flex", flexDirection: "column", gap: 3, fontSize: 11 }}>
              <div style={{ display: "flex", justifyContent: "space-between" }}>
                <span style={{ color: "rgb(107, 114, 128)" }}>Model</span>
                <span>{trackedFlightPopup.model || "Unknown"}</span>
              </div>
              <div style={{ display: "flex", justifyContent: "space-between" }}>
                <span style={{ color: "rgb(107, 114, 128)" }}>Altitude</span>
                <span>{trackedFlightPopup.alt.toLocaleString()} ft</span>
              </div>
              <div style={{ display: "flex", justifyContent: "space-between" }}>
                <span style={{ color: "rgb(107, 114, 128)" }}>Speed</span>
                <span>{trackedFlightPopup.speed_knots.toFixed(0)} kn</span>
              </div>
              <div style={{ display: "flex", justifyContent: "space-between" }}>
                <span style={{ color: "rgb(107, 114, 128)" }}>Country</span>
                <span>{trackedFlightPopup.country || "Unknown"}</span>
              </div>
            </div>
          </div>
        </Popup>
      )}

      {kiwisdrPopup && (
        <Popup
          longitude={kiwisdrPopup.lng}
          latitude={kiwisdrPopup.lat}
          onClose={() => setKiwisdrPopup(null)}
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
                color: "#14b8a6",
              }}
            >
              {kiwisdrPopup.location_name}
            </div>
            <div style={{ display: "flex", flexDirection: "column", gap: 3, fontSize: 11 }}>
              <div style={{ display: "flex", justifyContent: "space-between" }}>
                <span style={{ color: "rgb(107, 114, 128)" }}>Frequency</span>
                <span>{kiwisdrPopup.frequency || "—"}</span>
              </div>
              <div style={{ display: "flex", justifyContent: "space-between" }}>
                <span style={{ color: "rgb(107, 114, 128)" }}>Band</span>
                <span>{kiwisdrPopup.band || "—"}</span>
              </div>
            </div>
          </div>
        </Popup>
      )}

      {gpsJammingPopup && (
        <Popup
          longitude={gpsJammingPopup.lng}
          latitude={gpsJammingPopup.lat}
          onClose={() => setGpsJammingPopup(null)}
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
                Severity: {gpsJammingPopup.severity}
              </span>
            </div>
            <div style={{ display: "flex", flexDirection: "column", gap: 3, fontSize: 11 }}>
              <div style={{ display: "flex", justifyContent: "space-between" }}>
                <span style={{ color: "rgb(107, 114, 128)" }}>Region</span>
                <span>{gpsJammingPopup.region || "Unknown"}</span>
              </div>
              <div style={{ display: "flex", justifyContent: "space-between" }}>
                <span style={{ color: "rgb(107, 114, 128)" }}>Source</span>
                <span>{gpsJammingPopup.source || "Unknown"}</span>
              </div>
              <div style={{ display: "flex", justifyContent: "space-between" }}>
                <span style={{ color: "rgb(107, 114, 128)" }}>Area</span>
                <span>{gpsJammingPopup.affected_area_km.toLocaleString()} km</span>
              </div>
            </div>
          </div>
        </Popup>
      )}

      {earthquakePopup && (
        <Popup
          longitude={earthquakePopup.lng}
          latitude={earthquakePopup.lat}
          onClose={() => setEarthquakePopup(null)}
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
                color: "#b91c1c",
              }}
            >
              {earthquakePopup.place}
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
                M {earthquakePopup.mag.toFixed(1)}
              </span>
            </div>
            <div style={{ display: "flex", flexDirection: "column", gap: 3, fontSize: 11 }}>
              <div style={{ display: "flex", justifyContent: "space-between" }}>
                <span style={{ color: "rgb(107, 114, 128)" }}>Depth</span>
                <span>{earthquakePopup.depth_km.toFixed(1)} km</span>
              </div>
              <div style={{ display: "flex", justifyContent: "space-between" }}>
                <span style={{ color: "rgb(107, 114, 128)" }}>Time</span>
                <span>{earthquakePopup.time || "—"}</span>
              </div>
            </div>
          </div>
        </Popup>
      )}

      {powerPlantPopup && (
        <Popup
          longitude={powerPlantPopup.lng}
          latitude={powerPlantPopup.lat}
          onClose={() => setPowerPlantPopup(null)}
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
                color: "#f59e0b",
              }}
            >
              {powerPlantPopup.name}
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
                {powerPlantPopup.fuel_type}
              </span>
            </div>
            <div style={{ display: "flex", flexDirection: "column", gap: 3, fontSize: 11 }}>
              <div style={{ display: "flex", justifyContent: "space-between" }}>
                <span style={{ color: "rgb(107, 114, 128)" }}>Capacity</span>
                <span>{powerPlantPopup.capacity_mw.toLocaleString()} MW</span>
              </div>
              <div style={{ display: "flex", justifyContent: "space-between" }}>
                <span style={{ color: "rgb(107, 114, 128)" }}>Country</span>
                <span>{powerPlantPopup.country || "Unknown"}</span>
              </div>
            </div>
          </div>
        </Popup>
      )}

      {datacenterPopup && (
        <Popup
          longitude={datacenterPopup.lng}
          latitude={datacenterPopup.lat}
          onClose={() => setDatacenterPopup(null)}
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
                color: "#6366f1",
              }}
            >
              {datacenterPopup.name}
            </div>
            <div style={{ display: "flex", flexDirection: "column", gap: 3, fontSize: 11 }}>
              <div style={{ display: "flex", justifyContent: "space-between" }}>
                <span style={{ color: "rgb(107, 114, 128)" }}>Operator</span>
                <span>{datacenterPopup.operator || "Unknown"}</span>
              </div>
              <div style={{ display: "flex", justifyContent: "space-between" }}>
                <span style={{ color: "rgb(107, 114, 128)" }}>Country</span>
                <span>{datacenterPopup.country || "Unknown"}</span>
              </div>
            </div>
          </div>
        </Popup>
      )}

      {internetOutagePopup && (
        <Popup
          longitude={internetOutagePopup.lng}
          latitude={internetOutagePopup.lat}
          onClose={() => setInternetOutagePopup(null)}
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
                color: "#7c3aed",
              }}
            >
              {internetOutagePopup.region_name}
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
                Severity: {internetOutagePopup.severity}
              </span>
            </div>
            <div style={{ display: "flex", flexDirection: "column", gap: 3, fontSize: 11 }}>
              <div style={{ display: "flex", justifyContent: "space-between" }}>
                <span style={{ color: "rgb(107, 114, 128)" }}>Provider</span>
                <span>{internetOutagePopup.provider || "Unknown"}</span>
              </div>
              <div style={{ display: "flex", justifyContent: "space-between" }}>
                <span style={{ color: "rgb(107, 114, 128)" }}>Affected Users</span>
                <span>{internetOutagePopup.affected_users.toLocaleString()}</span>
              </div>
            </div>
          </div>
        </Popup>
      )}
    </Map>
  );
}
