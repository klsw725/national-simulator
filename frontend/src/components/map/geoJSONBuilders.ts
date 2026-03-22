import type {
  Ship,
  Flight,
  Satellite,
  MilitaryBase,
  UAV,
  CCTV,
  KiwiSDR,
  GPSJamming,
  Earthquake,
  FIRMSFire,
  PowerPlant,
  Datacenter,
  InternetOutage,
} from "@/types/dashboard";

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

export function buildUAVsGeoJSON(
  uavs: UAV[]
): GeoJSON.FeatureCollection<GeoJSON.Point> {
  return {
    type: "FeatureCollection",
    features: uavs
      .filter((u) => u.lat != null && u.lng != null)
      .map((u) => ({
        type: "Feature" as const,
        geometry: {
          type: "Point" as const,
          coordinates: [u.lng, u.lat],
        },
        properties: {
          callsign: u.callsign,
          country: u.country,
          uav_type: u.uav_type,
          aircraft_model: u.aircraft_model,
          alt: u.alt,
        },
      })),
  };
}

export function buildTrackedFlightsGeoJSON(
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
          model: f.model,
          alt: f.alt,
          speed_knots: f.speed_knots,
          heading: f.heading ?? 0,
        },
      })),
  };
}

export function buildCCTVGeoJSON(
  cameras: CCTV[]
): GeoJSON.FeatureCollection<GeoJSON.Point> {
  return {
    type: "FeatureCollection",
    features: cameras
      .filter((c) => c.lat != null && c.lon != null)
      .map((c) => ({
        type: "Feature" as const,
        geometry: {
          type: "Point" as const,
          coordinates: [c.lon, c.lat],
        },
        properties: {
          camera_id: c.camera_id,
          location_name: c.location_name,
          country: c.country,
        },
      })),
  };
}

export function buildKiwiSDRGeoJSON(
  nodes: KiwiSDR[]
): GeoJSON.FeatureCollection<GeoJSON.Point> {
  return {
    type: "FeatureCollection",
    features: nodes
      .filter((n) => n.lat != null && n.lon != null)
      .map((n) => ({
        type: "Feature" as const,
        geometry: {
          type: "Point" as const,
          coordinates: [n.lon, n.lat],
        },
        properties: {
          node_id: n.node_id,
          location_name: n.location_name,
        },
      })),
  };
}

export function buildGPSJammingGeoJSON(
  zones: GPSJamming[]
): GeoJSON.FeatureCollection<GeoJSON.Point> {
  return {
    type: "FeatureCollection",
    features: zones
      .filter((z) => z.lat != null && z.lng != null)
      .map((z) => ({
        type: "Feature" as const,
        geometry: {
          type: "Point" as const,
          coordinates: [z.lng, z.lat],
        },
        properties: {
          severity: z.severity,
          affected_count: z.affected_count,
        },
      })),
  };
}

export function buildEarthquakesGeoJSON(
  quakes: Earthquake[]
): GeoJSON.FeatureCollection<GeoJSON.Point> {
  return {
    type: "FeatureCollection",
    features: quakes
      .filter((q) => q.lat != null && q.lng != null)
      .map((q) => ({
        type: "Feature" as const,
        geometry: {
          type: "Point" as const,
          coordinates: [q.lng, q.lat],
        },
        properties: {
          id: q.id,
          mag: q.mag,
          place: q.place,
        },
      })),
  };
}

export function buildFiresGeoJSON(
  fires: FIRMSFire[]
): GeoJSON.FeatureCollection<GeoJSON.Point> {
  return {
    type: "FeatureCollection",
    features: fires
      .filter((f) => f.lat != null && f.lng != null)
      .map((f) => ({
        type: "Feature" as const,
        geometry: {
          type: "Point" as const,
          coordinates: [f.lng, f.lat],
        },
        properties: {
          frp: f.frp,
          confidence: f.confidence,
        },
      })),
  };
}

export function buildPowerPlantsGeoJSON(
  plants: PowerPlant[]
): GeoJSON.FeatureCollection<GeoJSON.Point> {
  return {
    type: "FeatureCollection",
    features: plants
      .filter((p) => p.lat != null && p.lng != null)
      .map((p) => ({
        type: "Feature" as const,
        geometry: {
          type: "Point" as const,
          coordinates: [p.lng, p.lat],
        },
        properties: {
          name: p.name,
          country: p.country,
          fuel_type: p.fuel_type,
          capacity_mw: p.capacity_mw,
        },
      })),
  };
}

export function buildDatacentersGeoJSON(
  dcs: Datacenter[]
): GeoJSON.FeatureCollection<GeoJSON.Point> {
  return {
    type: "FeatureCollection",
    features: dcs
      .filter((d) => d.lat != null && d.lng != null)
      .map((d) => ({
        type: "Feature" as const,
        geometry: {
          type: "Point" as const,
          coordinates: [d.lng, d.lat],
        },
        properties: {
          name: d.name,
          company: d.company,
          country: d.country,
        },
      })),
  };
}

export function buildInternetOutagesGeoJSON(
  outages: InternetOutage[]
): GeoJSON.FeatureCollection<GeoJSON.Point> {
  return {
    type: "FeatureCollection",
    features: outages
      .filter((o) => o.lat != null && o.lng != null)
      .map((o) => ({
        type: "Feature" as const,
        geometry: {
          type: "Point" as const,
          coordinates: [o.lng, o.lat],
        },
        properties: {
          region_name: o.region_name,
          country_name: o.country_name,
          severity: o.severity,
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
