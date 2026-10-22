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
  origin?: { latitude: number; longitude: number; label?: string };
  destination?: { latitude: number; longitude: number; label?: string };
  via?: Array<{ latitude: number; longitude: number; label?: string }>;
  show_warnings?: boolean;
};

export type RouteView = {
  vehicle_id: string;
  state?: string;
  provider?: string;
  distance_m?: number;
  duration_s?: number;
  geometry?: Array<{ latitude: number; longitude: number }>;
  warnings?: string[];
  beta?: boolean;
  origin?: RoutePoint;
  destination?: RoutePoint;
  via?: RoutePoint[];
  route_input?: { origin?: RoutePoint; destination?: RoutePoint; via?: RoutePoint[] };
  error?: string;
  metadata?: { tolls?: { total?: number | null; currency?: string | null; status?: string; estimate?: boolean | null } | null };
};

export type RoutePoint = { latitude: number; longitude: number; label?: string };

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

export function renderRouteHtml(route: RouteView | undefined, config: CardConfig): string {
  if (route?.state === "error") return `<p class="route-error" role="alert">${escapeHtml(route.error ?? "Route konnte nicht berechnet werden.")}</p>`;
  if (!route || route.state !== "ready") return `<p class="route-empty" role="status">Keine berechnete Route vorhanden.</p>`;
  const distance = route.distance_m == null ? "–" : `${(route.distance_m / 1000).toFixed(1)} km`;
  const duration = route.duration_s == null ? "–" : `${Math.round(route.duration_s / 60)} min`;
  const warnings = config.show_warnings === false ? "" : (route.warnings ?? []).map((warning) => `<li>${escapeHtml(warning)}</li>`).join("");
  const points = route.geometry ?? [];
  const map = points.length > 1
    ? `<svg class="route-map" viewBox="0 0 320 120" role="img" aria-label="Routenverlauf"><polyline points="${points.map((point, index) => `${(index / (points.length - 1)) * 300 + 10},${110 - (index % 2) * 45}`).join(" ")}" fill="none" stroke="var(--primary-color,#03a9f4)" stroke-width="5" stroke-linecap="round" /></svg>`
    : "";
  const tolls = route.metadata?.tolls;
  const tollText = tolls ? ` · Maut: ${tolls.total == null ? "unbekannt" : `${tolls.total.toFixed(2)} ${tolls.currency ?? "EUR"}`}${tolls.estimate ? " (Schätzung)" : ""}` : "";
  return `${map}<p class="route-summary"><strong>${distance}</strong> · ${duration} · ${escapeHtml(route.provider ?? "unbekannt")}${tollText}</p>${warnings ? `<ul class="route-warnings">${warnings}</ul>` : ""}`;
}

export function buildNavigationLink(origin: RoutePoint | undefined, destination: RoutePoint | undefined): string | null {
  if (!destination || !Number.isFinite(destination.latitude) || !Number.isFinite(destination.longitude)) return null;
  const to = `${destination.latitude},${destination.longitude}`;
  const from = origin && Number.isFinite(origin.latitude) && Number.isFinite(origin.longitude) ? `${origin.latitude},${origin.longitude}` : "";
  if (typeof navigator !== "undefined" && /iPad|iPhone|iPod/.test(navigator.userAgent)) return `maps://?daddr=${encodeURIComponent(to)}${from ? `&saddr=${encodeURIComponent(from)}` : ""}`;
  if (typeof navigator !== "undefined" && /Android/.test(navigator.userAgent)) return `geo:${encodeURIComponent(to)}?q=${encodeURIComponent(to)}`;
  return `https://www.openstreetmap.org/directions?engine=fossgis_osrm_car&route=${encodeURIComponent(`${from ? `${from};` : ""}${to}`)}`;
}

export function buildGpx(route: RouteView, origin: RoutePoint, destination: RoutePoint, via: RoutePoint[], mode: "route" | "track" | "combined"): string {
  const point = (value: RoutePoint, tag: string): string => `<${tag} lat="${value.latitude}" lon="${value.longitude}" />`;
  const routePoints = [origin, ...via, destination];
  const routeXml = `<rte>${routePoints.map((value) => point(value, "rtept")).join("")}</rte>`;
  const geometry = route.geometry ?? [];
  const trackXml = `<trk><trkseg>${geometry.map((value) => point(value, "trkpt")).join("")}</trkseg></trk>`;
  const body = mode === "route" ? routeXml : mode === "track" ? trackXml : `${routeXml}${trackXml}`;
  return `<?xml version="1.0" encoding="UTF-8"?><gpx xmlns="http://www.topografix.com/GPX/1/1" version="1.1" creator="SmartCamper Suite"><metadata><name>SmartCamper Route</name></metadata>${body}</gpx>`;
}

export function downloadGpx(route: RouteView, origin: RoutePoint, destination: RoutePoint, via: RoutePoint[], mode: "route" | "track" | "combined"): void {
  const blob = new Blob([buildGpx(route, origin, destination, via, mode)], { type: "application/gpx+xml;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = `smartcamper-route-${mode}.gpx`;
  anchor.rel = "noopener";
  anchor.click();
  setTimeout(() => URL.revokeObjectURL(url), 0);
}

const MODULES = new Set(["travel_journal", "fuel_stations", "route_planner", "border_forecast"]);

export function validateConfig(config: CardConfig): CardConfig {
  if (!MODULES.has(config.module)) throw new Error("Unknown SmartCamper module");
  return config;
}
