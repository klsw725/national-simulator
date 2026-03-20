"use client";

import { useEffect } from "react";
import type { MapRef } from "react-map-gl/maplibre";

export function useImperativeSource(
  map: MapRef | null,
  sourceId: string,
  geojson: GeoJSON.FeatureCollection | null
) {
  useEffect(() => {
    if (!map) return;
    const src = map.getSource(sourceId) as ReturnType<
      typeof map.getSource
    > & { setData?: (data: GeoJSON.FeatureCollection) => void };
    if (src && typeof src.setData === "function") {
      src.setData(
        geojson || { type: "FeatureCollection" as const, features: [] }
      );
    }
  }, [map, sourceId, geojson]);
}
