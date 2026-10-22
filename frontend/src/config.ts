export type CardConfig = {
  type: string;
  module: string;
  vehicle_id?: string;
  display_mode?: "detailed" | "compact" | "individual";
  show_address?: boolean;
  show_status?: boolean;
};

export type FuelStationView = {
  station_id: string;
  name: string;
  price?: number | null;
  distance_km?: number | null;
  address?: string;
  is_open?: boolean | null;
  provider?: string;
  fuel_type?: string;
  brand?: string;
};

export function selectVehicle(
  config: CardConfig,
  states: Record<string, { attributes?: { vehicle_id?: string } }>,
): string | undefined {
  if (config.vehicle_id) return config.vehicle_id;
  return Object.values(states).find((state) => state.attributes?.vehicle_id)?.attributes?.vehicle_id;
}

export function escapeHtml(value: string): string {
  return value.replace(/[&<>"']/g, (character) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
  } as Record<string, string>)[character] ?? character);
}

export function renderFuelStationsHtml(
  stations: FuelStationView[],
  config: CardConfig,
): string {
  const mode = config.display_mode ?? "detailed";
  if (!stations.length) return `<p class="fuel-empty">Keine Tankstellen verfügbar</p>`;
  return stations.map((station) => {
    const price = station.price == null ? "–" : `${station.price.toFixed(3)} €`;
    const distance = station.distance_km == null ? "–" : `${station.distance_km.toFixed(1)} km`;
    const address = config.show_address === false ? "" : `<small>${escapeHtml(station.address ?? "")}</small>`;
    const status = config.show_status === false ? "" : `<span>${station.is_open === false ? "Geschlossen" : "Offen/unbekannt"}</span>`;
    return `<li class="fuel-station ${mode}"><strong>${escapeHtml(station.name)}</strong><b>${price}</b><em>${distance}</em>${address}${status}</li>`;
  }).join("");
}

const MODULES = new Set(["travel_journal", "fuel_stations", "route_planner", "border_forecast"]);

export function validateConfig(config: CardConfig): CardConfig {
  if (!MODULES.has(config.module)) throw new Error("Unknown SmartCamper module");
  return config;
}
