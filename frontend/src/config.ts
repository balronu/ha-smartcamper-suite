export type CardConfig = {
  type: string;
  module: string;
  vehicle_id?: string;
  display_mode?: "detailed" | "compact" | "individual";
  sort_mode?: "distance" | "price";
  visible_station_count?: number;
  show_address?: boolean;
  show_distance?: boolean;
  show_prices?: boolean;
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
  fuel_prices?: Record<string, number | null>;
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
  const sorted = [...stations].sort((left, right) => {
    const leftValue = config.sort_mode === "price" ? left.price : left.distance_km;
    const rightValue = config.sort_mode === "price" ? right.price : right.distance_km;
    return (leftValue ?? Number.POSITIVE_INFINITY) - (rightValue ?? Number.POSITIVE_INFINITY);
  });
  const visible = Number.isInteger(config.visible_station_count) && (config.visible_station_count ?? 0) > 0
    ? sorted.slice(0, config.visible_station_count)
    : sorted;
  return visible.map((station) => {
    const prices = station.fuel_prices
      ? Object.entries(station.fuel_prices).map(([fuel, value]) => `${fuel.toUpperCase()}: ${value == null ? "–" : `${value.toFixed(3)} €`}`).join(" · ")
      : station.price == null ? "–" : `${station.price.toFixed(3)} €`;
    const price = config.show_prices === false ? "" : `<b>${prices}</b>`;
    const distance = config.show_distance === false ? "" : `<em>${station.distance_km == null ? "–" : `${station.distance_km.toFixed(1)} km`}</em>`;
    const address = config.show_address === false ? "" : `<small>${escapeHtml(station.address ?? "")}</small>`;
    const status = config.show_status === false ? "" : `<span>${station.is_open === false ? "Geschlossen" : "Offen/unbekannt"}</span>`;
    return `<li class="fuel-station ${mode}"><strong>${escapeHtml(station.name)}</strong>${price}${distance}${address}${status}</li>`;
  }).join("");
}

export function renderFuelStateHtml(
  status: string | undefined,
  stations: FuelStationView[],
  config: CardConfig,
): string {
  if (status === "loading") return "<p class=\"fuel-loading\">Lade Tankstellen …</p>";
  if (status === "error") return "<p class=\"fuel-error\">Tankstellen konnten nicht geladen werden.</p>";
  return renderFuelStationsHtml(stations, config);
}

const MODULES = new Set(["travel_journal", "fuel_stations", "route_planner", "border_forecast"]);

export function validateConfig(config: CardConfig): CardConfig {
  if (!MODULES.has(config.module)) throw new Error("Unknown SmartCamper module");
  return config;
}
