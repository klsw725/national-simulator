import type { Ship } from "@/types/dashboard";

function getIconId(type: string): string {
  if (type === "military_vessel" || type === "carrier") return "yellow";
  if (type === "cargo" || type === "tanker") return "red";
  return "blue";
}

export function buildShipsGeoJSON(
  ships: Ship[]
): GeoJSON.FeatureCollection<GeoJSON.Point> {
  return {
    type: "FeatureCollection",
    features: ships
      .filter((s) => s.lat != null && s.lng != null)
      .map((s) => ({
        type: "Feature" as const,
        geometry: {
          type: "Point" as const,
          coordinates: [s.lng, s.lat],
        },
        properties: {
          id: s.mmsi,
          name: s.name,
          type: s.type,
          iconId: getIconId(s.type),
          rotation: s.heading ?? 0,
          sog: s.sog,
          country: s.country,
        },
      })),
  };
}

export const EMPTY_FC: GeoJSON.FeatureCollection<GeoJSON.Point> = {
  type: "FeatureCollection",
  features: [],
};

export function buildSimulationActorsGeoJSON(
  geojson?: GeoJSON.FeatureCollection | null
): GeoJSON.FeatureCollection | null {
  if (!geojson?.features?.length) return null;
  return {
    type: "FeatureCollection",
    features: geojson.features.filter(
      (f) => f.properties?.feature_type === "actor"
    ),
  };
}

export function buildSimulationRelationsGeoJSON(
  geojson?: GeoJSON.FeatureCollection | null
): GeoJSON.FeatureCollection | null {
  if (!geojson?.features?.length) return null;
  return {
    type: "FeatureCollection",
    features: geojson.features.filter(
      (f) => f.properties?.feature_type === "relationship"
    ),
  };
}
