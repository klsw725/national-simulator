export interface Ship {
  mmsi: number;
  name: string;
  type: string; // military_vessel, carrier, cargo, tanker, passenger, yacht, other, unknown
  lat: number;
  lng: number;
  heading: number | null;
  sog: number;
  country: string;
  ais_type_code?: number;
}

export interface Flight {
  callsign: string;
  country: string;
  lat: number;
  lng: number;
  alt: number;
  heading: number | null;
  speed_knots: number;
  model: string;
  type: string;
  force?: string;
  military_type?: string;
}

export interface Satellite {
  id: string;
  name: string;
  country: string;
  mission: string;
  sat_type: string;
  lat: number;
  lng: number;
  alt_km: number;
}

export interface MilitaryBase {
  name: string;
  country: string;
  operator: string;
  branch: string;
  lat: number;
  lng: number;
}

export interface UAV {
  callsign: string;
  country: string;
  lat: number;
  lng: number;
  alt: number;
  uav_type: string; // HALE | MALE
  aircraft_model: string;
}

export interface CCTV {
  camera_id: string;
  lat: number;
  lon: number; // ⚠️ CCTV는 lon 사용 (AGENTS.md)
  location_name: string;
  country: string;
}

export interface KiwiSDR {
  node_id: string;
  lat: number;
  lon: number; // ⚠️ KiwiSDR는 lon 사용 (AGENTS.md)
  location_name: string;
}

export interface Earthquake {
  id: string;
  mag: number;
  lat: number;
  lng: number;
  place: string;
}

export interface PowerPlant {
  name: string;
  country: string;
  fuel_type: string;
  capacity_mw: number;
  lat: number;
  lng: number;
}

export interface Datacenter {
  name: string;
  company: string;
  country: string;
  lat: number;
  lng: number;
}

export interface GPSJamming {
  lat: number;
  lng: number;
  severity: number;
  affected_count: number;
}

export interface InternetOutage {
  region_name: string;
  country_name: string;
  severity: number;
  lat: number;
  lng: number;
}

export interface FIRMSFire {
  lat: number;
  lng: number;
  frp: number;
  confidence: string;
}

export interface SpaceWeather {
  kp_index: number;
  kp_text: string; // QUIET | UNSETTLED | ACTIVE | STORM
  events: Array<{
    type: string;
    begin: string;
    end: string;
  }>;
}

export interface LiveDataFast {
  ships: Ship[];
  commercial_flights?: Flight[];
  military_flights?: Flight[];
  private_flights?: Flight[];
  private_jets?: Flight[];
  tracked_flights?: Flight[];
  satellites?: Satellite[];
  cctv?: CCTV[];
  uavs?: UAV[];
  liveuamap?: unknown[];
  gps_jamming?: GPSJamming[];
  freshness?: Record<string, string>;
}

export interface LiveDataSlow {
  news?: unknown[];
  stocks?: unknown[];
  oil?: unknown;
  weather?: unknown;
  gdelt: unknown[];
  earthquakes?: Earthquake[];
  airports?: unknown[];
  kiwisdr?: KiwiSDR[];
  space_weather?: SpaceWeather | null;
  internet_outages?: InternetOutage[];
  firms_fires?: FIRMSFire[];
  datacenters?: Datacenter[];
  military_bases?: MilitaryBase[];
  power_plants?: PowerPlant[];
  frontlines?: unknown;
  freshness?: Record<string, string>;
}

export type BackendStatus = "connecting" | "connected" | "disconnected";

export interface PollingState {
  ships: Ship[];
  militaryFlights: Flight[];
  satellites: Satellite[];
  militaryBases: MilitaryBase[];
  uavs: UAV[];
  trackedFlights: Flight[];
  cctv: CCTV[];
  gpsJamming: GPSJamming[];
  liveuamap: unknown[];
  gdelt: unknown[];
  news: unknown[];
  stocks: unknown[];
  earthquakes: Earthquake[];
  kiwisdr: KiwiSDR[];
  internetOutages: InternetOutage[];
  firmsFires: FIRMSFire[];
  datacenters: Datacenter[];
  powerPlants: PowerPlant[];
  spaceWeather: SpaceWeather | null;
  frontlines: unknown;
  freshness: Record<string, string>;
  backendStatus: BackendStatus;
}
