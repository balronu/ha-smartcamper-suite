// src/config.ts
var DEFAULT_LOGO_PATH = "/smartcamper_suite/logos/";
function selectVehicle(config, states) {
  if (config.vehicle_id) return config.vehicle_id;
  return Object.values(states).find((state) => state.attributes?.vehicle_id)?.attributes?.vehicle_id;
}
function escapeHtml(value) {
  return value.replace(/[&<>"']/g, (character) => ({
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    '"': "&quot;",
    "'": "&#39;"
  })[character] ?? character);
}
function normalizedBrand(value) {
  return String(value ?? "").trim().toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "");
}
function buildBrandLogoUrl(brand, logoPath = DEFAULT_LOGO_PATH) {
  const key = normalizedBrand(brand);
  const base = String(logoPath ?? DEFAULT_LOGO_PATH).trim().replace(/\/+$/, "");
  return key && base ? `${base}/${encodeURIComponent(key)}.png` : null;
}
function buildNavigationUrl(latitude, longitude, provider = "auto", label = "Tankstelle") {
  const lat = Number(latitude);
  const lon = Number(longitude);
  if (!Number.isFinite(lat) || !Number.isFinite(lon)) return null;
  const destination = `${lat},${lon}`;
  if (provider === "apple") return `https://maps.apple.com/?daddr=${encodeURIComponent(destination)}&dirflg=d`;
  if (provider === "google") return `https://www.google.com/maps/dir/?api=1&destination=${encodeURIComponent(destination)}`;
  if (provider === "waze") return `https://waze.com/ul?ll=${encodeURIComponent(destination)}&navigate=yes`;
  return `https://www.google.com/maps/dir/?api=1&destination=${encodeURIComponent(destination)}&destination_place_id=${encodeURIComponent(label)}`;
}
function prioritizeStations(stations, sortMode = "distance") {
  return [...stations].sort((left, right) => {
    const leftValue = sortMode === "price" ? left.price : left.distance_km;
    const rightValue = sortMode === "price" ? right.price : right.distance_km;
    return (leftValue ?? Number.POSITIVE_INFINITY) - (rightValue ?? Number.POSITIVE_INFINITY) || String(left.station_id).localeCompare(String(right.station_id));
  });
}
function renderFuelStationsHtml(stations, config) {
  const mode = config.display_mode ?? "detailed";
  if (!stations.length) return `<p class="fuel-empty">Keine Tankstellen verf\xFCgbar</p>`;
  const sorted = prioritizeStations(stations, config.sort_mode);
  const visible = Number.isInteger(config.visible_station_count) && (config.visible_station_count ?? 0) > 0 ? sorted.slice(0, config.visible_station_count) : sorted;
  const highlightIds = config.custom_layout === "highlights_list" ? new Set(sorted.slice(0, 2).map((station) => station.station_id)) : /* @__PURE__ */ new Set();
  const renderStation = (station, highlight = false) => {
    const prices = station.fuel_prices ? Object.entries(station.fuel_prices).map(([fuel, value]) => `${fuel.toUpperCase()}: ${value == null ? "\u2013" : `${value.toFixed(3)} \u20AC`}`).join(" \xB7 ") : station.price == null ? "\u2013" : `${station.price.toFixed(3)} \u20AC`;
    const price = config.show_prices === false ? "" : `<b class="prices">${prices}</b>`;
    const distance = config.show_distance === false ? "" : `<em>${station.distance_km == null ? "\u2013" : `${station.distance_km.toFixed(1)} km`}</em>`;
    const address = config.show_address === false ? "" : `<small>${escapeHtml(station.address ?? "")}</small>`;
    const status = config.show_status === false ? "" : `<span>${station.is_open === false ? "Geschlossen" : "Offen/unbekannt"}</span>`;
    const logoUrl = config.show_brand_logos !== false ? buildBrandLogoUrl(station.brand, config.logo_path) : null;
    const logo = logoUrl ? `<img class="brand-logo" src="${escapeHtml(logoUrl)}" alt="${escapeHtml(station.brand ?? "")} Logo" />` : `<span class="brand-logo-fallback" aria-hidden="true">\u26FD</span>`;
    const navigation = config.navigation !== false ? buildNavigationUrl(station.latitude, station.longitude, config.navigation_provider, station.name) : null;
    const navigate = navigation ? `<a class="navigate" href="${escapeHtml(navigation)}" target="_blank" rel="noopener noreferrer" aria-label="Navigieren">\u2197</a>` : "";
    const badge = config.show_badges !== false && highlight ? `<span class="badge">Highlight</span>` : "";
    return `<li class="fuel-station ${mode}${highlight ? " highlight" : ""}" data-station-id="${escapeHtml(station.station_id)}">${logo}<div class="station-main"><strong>${escapeHtml(station.name)}</strong>${badge}${address}<div class="meta">${status}${distance}</div></div>${price}${navigate}</li>`;
  };
  const highlights = config.custom_layout === "highlights_list" ? sorted.slice(0, 2).map((station) => renderStation(station, true)).join("") : "";
  const remaining = config.custom_layout === "highlights_list" ? visible.filter((station) => !highlightIds.has(station.station_id)) : visible;
  return `${highlights ? `<section class="highlights" aria-label="Highlights">${highlights}</section>` : ""}<ul class="stations">${remaining.map((station) => renderStation(station)).join("")}</ul>`;
}
function renderFuelStateHtml(status, stations, config) {
  if (status === "loading") return '<p class="fuel-loading" role="status">Lade Tankstellen \u2026</p>';
  if (status === "error") return '<p class="fuel-error" role="alert">Tankstellen konnten nicht geladen werden.</p>';
  return renderFuelStationsHtml(stations, config);
}
var MODULES = /* @__PURE__ */ new Set(["travel_journal", "fuel_stations", "route_planner", "border_forecast"]);
function validateConfig(config) {
  if (!MODULES.has(config.module)) throw new Error("Unknown SmartCamper module");
  return config;
}

// src/smartcamper-card.ts
var SmartCamperCard = class extends HTMLElement {
  config = { type: "custom:smartcamper-card", module: "travel_journal" };
  _hass;
  setConfig(raw) {
    this.config = validateConfig(raw);
    this.render();
  }
  set hass(value) {
    this._hass = value;
    this.render();
  }
  get hass() {
    return this._hass;
  }
  getConfigElement() {
    const editor = document.createElement("div");
    editor.innerHTML = `
      <label>Modul <select data-field="module">
        <option value="travel_journal">Camper Travel Journal</option>
        <option value="fuel_stations">Mobile Fuel Stations</option>
        <option value="route_planner">Camper Route Planner</option>
        <option value="border_forecast">Wartezeiten Forecast</option>
      </select></label>
      <label>Fahrzeug <input data-field="vehicle_id" placeholder="Fahrzeug-ID (optional)" /></label>
      <label>Darstellung <select data-field="display_mode"><option value="detailed">Detailed</option><option value="compact">Compact</option><option value="individual">Individual</option></select></label>
      <label>Layout <select data-field="custom_layout"><option value="list">Liste</option><option value="highlights_list">Highlights + Liste</option><option value="configured_list">Konfiguriert</option></select></label>
      <label>Sortierung <select data-field="sort_mode"><option value="distance">Entfernung</option><option value="price">Preis</option></select></label>
      <label>Anzahl <input data-field="visible_station_count" type="number" min="0" /></label>
      <label>Navigation <select data-field="navigation_provider"><option value="auto">Automatisch</option><option value="apple">Apple</option><option value="google">Google</option><option value="waze">Waze</option></select></label>
      <label><input data-field="show_prices" type="checkbox" checked /> Preise</label>
      <label><input data-field="show_distance" type="checkbox" checked /> Entfernung</label>
      <label><input data-field="show_address" type="checkbox" checked /> Adresse</label>
      <label><input data-field="show_status" type="checkbox" checked /> Status</label>
      <label><input data-field="show_brand_logos" type="checkbox" checked /> Anbieterlogos</label>
      <label><input data-field="show_diagnostics" type="checkbox" checked /> Diagnostik</label>
      <label><input data-field="show_refresh" type="checkbox" checked /> Aktualisieren</label>`;
    const emit = () => {
      const module = editor.querySelector("[data-field=module]").value;
      const vehicle_id = editor.querySelector("[data-field=vehicle_id]").value || void 0;
      const sort_mode = editor.querySelector("[data-field=sort_mode]").value;
      const display_mode = editor.querySelector("[data-field=display_mode]").value;
      const custom_layout = editor.querySelector("[data-field=custom_layout]").value;
      const navigation_provider = editor.querySelector("[data-field=navigation_provider]").value;
      const visible_station_count = Number(editor.querySelector("[data-field=visible_station_count]").value) || 0;
      const bool = (field) => editor.querySelector(`[data-field=${field}]`).checked;
      editor.dispatchEvent(new CustomEvent("config-changed", {
        bubbles: true,
        composed: true,
        detail: { config: { ...this.config, module, vehicle_id, display_mode, custom_layout, sort_mode, navigation_provider, visible_station_count, navigation: true, show_prices: bool("show_prices"), show_distance: bool("show_distance"), show_address: bool("show_address"), show_status: bool("show_status"), show_brand_logos: bool("show_brand_logos"), show_diagnostics: bool("show_diagnostics"), show_refresh: bool("show_refresh") } }
      }));
    };
    editor.querySelectorAll("select, input").forEach((element) => element.addEventListener("change", emit));
    return editor;
  }
  getStubConfig() {
    return { type: "custom:smartcamper-card", module: "fuel_stations" };
  }
  getCardSize() {
    return 4;
  }
  render() {
    if (!this.isConnected && typeof document === "undefined") return;
    if (this.config.module !== "fuel_stations") {
      this.innerHTML = `<article><strong>SmartCamper Suite</strong><p>${this.config.module}</p><small>Modul ist vorbereitet.</small></article>`;
      return;
    }
    const states = this._hass?.states ?? {};
    const vehicleId = selectVehicle(this.config, states);
    const sensor = Object.values(states).find((state) => state.attributes?.vehicle_id === vehicleId);
    const status = sensor?.attributes?.state;
    const stations = this.mergeStations(sensor?.attributes?.stations ?? []);
    const stationHtml = renderFuelStateHtml(status, stations, this.config);
    const usage = sensor?.attributes?.provider_usage;
    const usageText = usage ? Object.entries(usage).map(([provider, value]) => `${provider}: ${value.quotas?.cheap?.remaining ?? "?"} verbleibend`).join(" \xB7 ") : "";
    const diagnostics = this.config.show_diagnostics !== false && (sensor?.attributes?.error || usageText) ? `<p class="diagnostics" role="status">${sensor?.attributes?.error ? `Providerfehler: ${String(sensor.attributes.error)}` : ""}${usageText ? ` ${usageText}` : ""}</p>` : "";
    const lastUpdated = this.config.show_last_updated !== false && sensor?.attributes?.updated_at ? `<small class="updated">Stand: ${String(sensor.attributes.updated_at)}</small>` : "";
    const refresh = this.config.show_refresh !== false && this.config.fetch_mode === "manual" ? `<button class="refresh" type="button">Jetzt aktualisieren</button>` : "";
    this.innerHTML = `<article class="fuel-card"><header>${this.config.show_title === false ? "" : "<strong>Tankstellen</strong>"}<small>${vehicleId ?? "Kein Fahrzeug ausgew\xE4hlt"}</small>${lastUpdated}${refresh}</header>${diagnostics}<div>${stationHtml}</div></article>`;
    this.querySelector(".refresh")?.addEventListener("click", () => {
      if (vehicleId && this._hass?.callService) void this._hass.callService("smartcamper_suite", "refresh_fuel_stations", { vehicle_id: vehicleId });
    });
  }
  mergeStations(raw) {
    const merged = /* @__PURE__ */ new Map();
    for (const station of raw) {
      const current = merged.get(station.station_id);
      if (!current) {
        merged.set(station.station_id, { ...station, fuel_prices: station.fuel_type ? { [station.fuel_type]: station.price ?? null } : station.fuel_prices });
        continue;
      }
      current.fuel_prices = { ...current.fuel_prices ?? {}, ...station.fuel_type ? { [station.fuel_type]: station.price ?? null } : station.fuel_prices ?? {} };
    }
    return [...merged.values()];
  }
};
if (typeof window !== "undefined" && typeof customElements !== "undefined") {
  if (!customElements.get("smartcamper-card")) customElements.define("smartcamper-card", SmartCamperCard);
  const cards = window.customCards ?? [];
  if (!cards.some((card) => card.type === "smartcamper-card")) {
    cards.push({ type: "smartcamper-card" });
    window.customCards = cards;
  }
}
