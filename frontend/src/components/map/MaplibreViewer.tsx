"use client";

import { useCallback, useRef } from "react";
import Map, {
  Source,
  Layer,
  type MapRef,
  type ViewStateChangeEvent,
} from "react-map-gl/maplibre";
import maplibregl from "maplibre-gl";
import { darkStyle } from "./styles/mapStyles";
import { useImperativeSource } from "@/hooks/useImperativeSource";
import { EMPTY_FC } from "./geoJSONBuilders";

interface MaplibreViewerProps {
  shipsGeoJSON: GeoJSON.FeatureCollection<GeoJSON.Point>;
}

const INITIAL_VIEW = {
  longitude: 115,
  latitude: 15,
  zoom: 4,
};

export default function MaplibreViewer({ shipsGeoJSON }: MaplibreViewerProps) {
  const mapRef = useRef<MapRef>(null);

  useImperativeSource(mapRef.current, "ships", shipsGeoJSON);

  const onLoad = useCallback(() => {
    const map = mapRef.current;
    if (!map) return;

    // Create ship icon images (simple colored circles)
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

      // Ship triangle pointing up
      ctx.fillStyle = color;
      ctx.beginPath();
      ctx.moveTo(size / 2, 2);
      ctx.lineTo(size - 3, size - 2);
      ctx.lineTo(3, size - 2);
      ctx.closePath();
      ctx.fill();

      // Outline
      ctx.strokeStyle = "rgba(0,0,0,0.5)";
      ctx.lineWidth = 1;
      ctx.stroke();

      map.addImage(
        `ship-${name}`,
        { width: size, height: size, data: ctx.getImageData(0, 0, size, size).data },
        { sdf: false }
      );
    }
  }, []);

  const onMove = useCallback((_evt: ViewStateChangeEvent) => {
    // placeholder for future viewport-based filtering
  }, []);

  return (
    <Map
      ref={mapRef}
      mapLib={maplibregl}
      initialViewState={INITIAL_VIEW}
      style={{ width: "100%", height: "100%" }}
      mapStyle={darkStyle}
      onLoad={onLoad}
      onMove={onMove}
      attributionControl={false}
    >
      <Source
        id="ships"
        type="geojson"
        data={shipsGeoJSON ?? EMPTY_FC}
        cluster={true}
        clusterMaxZoom={4}
        clusterRadius={50}
      >
        {/* Cluster circles */}
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
        {/* Cluster count label */}
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
        {/* Individual ship icons */}
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
    </Map>
  );
}
