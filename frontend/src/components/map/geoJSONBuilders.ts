import type { Ship, Flight, Satellite, MilitaryBase } from "@/types/dashboard";

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

export function buildMilitaryFlightsGeoJSON(
  flights: Flight[]
): GeoJSON.FeatureCollection<GeoJSON.Point> {
  return {
    type: "FeatureCollection",
    features: flights
      .filter((f) => f.lat != null && f.lng != null)
      .map((f) => ({
        type: "Feature" as const,
        geometry: {
          type: "Point" as const,
          coordinates: [f.lng, f.lat],
        },
        properties: {
          callsign: f.callsign,
          country: f.country,
          force: f.force ?? "",
          military_type: f.military_type ?? "",
          model: f.model,
          alt: f.alt,
          speed_knots: f.speed_knots,
          heading: f.heading ?? 0,
        },
      })),
  };
}

export function buildSatellitesGeoJSON(
  sats: Satellite[]
): GeoJSON.FeatureCollection<GeoJSON.Point> {
  return {
    type: "FeatureCollection",
    features: sats
      .filter((s) => s.lat != null && s.lng != null)
      .map((s) => ({
        type: "Feature" as const,
        geometry: {
          type: "Point" as const,
          coordinates: [s.lng, s.lat],
        },
        properties: {
          id: s.id,
          name: s.name,
          country: s.country,
          mission: s.mission,
          sat_type: s.sat_type,
          alt_km: s.alt_km,
        },
      })),
  };
}

export function buildMilitaryBasesGeoJSON(
  bases: MilitaryBase[]
): GeoJSON.FeatureCollection<GeoJSON.Point> {
  return {
    type: "FeatureCollection",
    features: bases
      .filter((b) => b.lat != null && b.lng != null)
      .map((b) => ({
        type: "Feature" as const,
        geometry: {
          type: "Point" as const,
          coordinates: [b.lng, b.lat],
        },
        properties: {
          name: b.name,
          country: b.country,
          branch: b.branch,
          operator: b.operator,
        },
      })),
  };
}

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
