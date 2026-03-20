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

export interface LiveDataFast {
  ships: Ship[];
}

export interface LiveDataSlow {
  gdelt: unknown[];
}

export type BackendStatus = "connecting" | "connected" | "disconnected";

export interface PollingState {
  ships: Ship[];
  gdelt: unknown[];
  backendStatus: BackendStatus;
}
