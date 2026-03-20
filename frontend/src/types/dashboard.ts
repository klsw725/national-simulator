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

export interface LiveDataFast {
  ships: Ship[];
  military_flights?: Flight[];
  satellites?: Satellite[];
}

export interface LiveDataSlow {
  gdelt: unknown[];
  military_bases?: MilitaryBase[];
}

export type BackendStatus = "connecting" | "connected" | "disconnected";

export interface PollingState {
  ships: Ship[];
  militaryFlights: Flight[];
  satellites: Satellite[];
  militaryBases: MilitaryBase[];
  gdelt: unknown[];
  backendStatus: BackendStatus;
}
