export type CardConfig = {
  type: string;
  module: string;
  vehicle_id?: string;
  display_mode?: "detailed" | "compact" | "individual";
  custom_layout?: "list" | "highlights_list" | "configured_list";
  sort_mode?: "distance" | "price";
  sort_fuel?: string;
  visible_station_count?: number;
  navigation?: boolean;
  navigation_provider?: "auto" | "apple" | "google" | "waze";
  show_brand_logos?: boolean;
  logo_path?: string;
  show_title?: boolean;
  show_name?: boolean;
  show_station_count?: boolean;
  show_radius?: boolean;
  show_fuel_type?: boolean;
  show_last_updated?: boolean;
  show_provider?: boolean;
  show_fetch_mode?: boolean;
  show_diagnostics?: boolean;
  show_refresh?: boolean;
  fetch_mode?: "automatic" | "manual";
  show_badges?: boolean;
  show_address?: boolean;
  show_distance?: boolean;
  show_prices?: boolean;
  show_status?: boolean;
  show_fuel_labels?: boolean;
  show_provider_row?: boolean;
  show_dividers?: boolean;
  density?: "normal" | "compact";
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
  latitude?: number | null;
  longitude?: number | null;
  price_stale?: boolean;
};

export const DEFAULT_LOGO_PATH = "/smartcamper_suite/logos/";

export function selectVehicle(config: CardConfig, states: Record<string, { attributes?: { vehicle_id?: string } }>): string | undefined {
  if (config.vehicle_id) return config.vehicle_id;
  return Object.values(states).find((state) => state.attributes?.vehicle_id)?.attributes?.vehicle_id;
}

export function escapeHtml(value: string): string {
  return value.replace(/[&<>"']/g, (character) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
  } as Record<string, string>)[character] ?? character);
}

function normalizedBrand(value: unknown): string {
  return String(value ?? "").trim().toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "");
}

export function buildBrandLogoUrl(brand: unknown, logoPath: unknown = DEFAULT_LOGO_PATH): string | null {
  const key = normalizedBrand(brand);
  const base = String(logoPath ?? DEFAULT_LOGO_PATH).trim().replace(/\/+$/, "");
  return key && base ? `${base}/${encodeURIComponent(key)}.png` : null;
}

export function buildNavigationUrl(latitude: unknown, longitude: unknown, provider: CardConfig["navigation_provider"] = "auto", label = "Tankstelle"): string | null {
  const lat = Number(latitude);
  const lon = Number(longitude);
  if (!Number.isFinite(lat) || !Number.isFinite(lon)) return null;
  const destination = `${lat},${lon}`;
  if (provider === "apple") return `https://maps.apple.com/?daddr=${encodeURIComponent(destination)}&dirflg=d`;
  if (provider === "google") return `https://www.google.com/maps/dir/?api=1&destination=${encodeURIComponent(destination)}`;
  if (provider === "waze") return `https://waze.com/ul?ll=${encodeURIComponent(destination)}&navigate=yes`;
  return `https://www.google.com/maps/dir/?api=1&destination=${encodeURIComponent(destination)}&destination_place_id=${encodeURIComponent(label)}`;
}

export function prioritizeStations(stations: FuelStationView[], sortMode: CardConfig["sort_mode"] = "distance", sortFuel?: string): FuelStationView[] {
  return [...stations].sort((left, right) => {
    const leftValue = sortMode === "price" ? (sortFuel ? left.fuel_prices?.[sortFuel] ?? left.price : left.price) : left.distance_km;
    const rightValue = sortMode === "price" ? (sortFuel ? right.fuel_prices?.[sortFuel] ?? right.price : right.price) : right.distance_km;
    return (leftValue ?? Number.POSITIVE_INFINITY) - (rightValue ?? Number.POSITIVE_INFINITY)
      || String(left.station_id).localeCompare(String(right.station_id));
  });
}

export function renderFuelStationsHtml(stations: FuelStationView[], config: CardConfig): string {
  const mode = config.display_mode ?? "detailed";
  if (!stations.length) return `<p class="fuel-empty">Keine Tankstellen verfügbar</p>`;
  const sorted = prioritizeStations(stations, config.sort_mode, config.sort_fuel);
  const visible = Number.isInteger(config.visible_station_count) && (config.visible_station_count ?? 0) > 0
    ? sorted.slice(0, config.visible_station_count) : sorted;
  const highlightIds = config.custom_layout === "highlights_list" ? new Set(sorted.slice(0, 2).map((station) => station.station_id)) : new Set<string>();
  const renderStation = (station: FuelStationView, highlight = false): string => {
    const prices = station.fuel_prices
      ? Object.entries(station.fuel_prices).map(([fuel, value]) => `${config.show_fuel_labels === false ? "" : `${fuel.toUpperCase()}: `}${value == null ? "–" : `${value.toFixed(3)} €`}`).join(" · ")
      : station.price == null ? "–" : `${station.price.toFixed(3)} €`;
    const price = config.show_prices === false ? "" : `<b class="prices">${prices}</b>`;
    const distance = config.show_distance === false ? "" : `<em>${station.distance_km == null ? "–" : `${station.distance_km.toFixed(1)} km`}</em>`;
    const address = config.show_address === false ? "" : `<small>${escapeHtml(station.address ?? "")}</small>`;
    const status = config.show_status === false ? "" : `<span>${station.is_open === false ? "Geschlossen" : "Offen/unbekannt"}</span>`;
    const provider = config.show_provider_row === false || !station.provider ? "" : `<span>${escapeHtml(station.provider)}</span>`;
    const logoUrl = config.show_brand_logos !== false ? buildBrandLogoUrl(station.brand, config.logo_path) : null;
    const logo = logoUrl ? `<img class="brand-logo" src="${escapeHtml(logoUrl)}" alt="${escapeHtml(station.brand ?? "")} Logo" />` : `<span class="brand-logo-fallback" aria-hidden="true">⛽</span>`;
    const navigation = config.navigation !== false ? buildNavigationUrl(station.latitude, station.longitude, config.navigation_provider, station.name) : null;
    const navigate = navigation ? `<a class="navigate" href="${escapeHtml(navigation)}" target="_blank" rel="noopener noreferrer" aria-label="Navigieren">↗</a>` : "";
    const badge = config.show_badges !== false && highlight ? `<span class="badge">Highlight</span>` : "";
    return `<li class="fuel-station ${mode}${highlight ? " highlight" : ""}" data-station-id="${escapeHtml(station.station_id)}">${logo}<div class="station-main">${config.show_name === false ? "" : `<strong>${escapeHtml(station.name)}</strong>`}${badge}${address}<div class="meta">${status}${distance}${provider}</div></div>${price}${navigate}</li>`;
  };
  const highlights = config.custom_layout === "highlights_list" ? sorted.slice(0, 2).map((station) => renderStation(station, true)).join("") : "";
  const remaining = config.custom_layout === "highlights_list" ? visible.filter((station) => !highlightIds.has(station.station_id)) : visible;
  return `${highlights ? `<section class="highlights" aria-label="Highlights">${highlights}</section>` : ""}<ul class="stations">${remaining.map((station) => renderStation(station)).join("")}</ul>`;
}

export function renderFuelStateHtml(status: string | undefined, stations: FuelStationView[], config: CardConfig): string {
  if (status === "loading") return "<p class=\"fuel-loading\" role=\"status\">Lade Tankstellen …</p>";
  if (status === "error") return "<p class=\"fuel-error\" role=\"alert\">Tankstellen konnten nicht geladen werden.</p>";
  return renderFuelStationsHtml(stations, config);
}

const MODULES = new Set(["travel_journal", "fuel_stations", "route_planner", "border_forecast"]);

export function validateConfig(config: CardConfig): CardConfig {
  if (!MODULES.has(config.module)) throw new Error("Unknown SmartCamper module");
  return config;
}
