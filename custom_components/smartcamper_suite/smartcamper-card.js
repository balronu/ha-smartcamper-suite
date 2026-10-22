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
function prioritizeStations(stations, sortMode = "distance", sortFuel) {
  return [...stations].sort((left, right) => {
    const leftValue = sortMode === "price" ? sortFuel ? left.fuel_prices?.[sortFuel] ?? left.price : left.price : left.distance_km;
    const rightValue = sortMode === "price" ? sortFuel ? right.fuel_prices?.[sortFuel] ?? right.price : right.price : right.distance_km;
    return (leftValue ?? Number.POSITIVE_INFINITY) - (rightValue ?? Number.POSITIVE_INFINITY) || String(left.station_id).localeCompare(String(right.station_id));
  });
}
function renderFuelStationsHtml(stations, config) {
  const mode = config.display_mode ?? "detailed";
  if (!stations.length) return `<p class="fuel-empty">Keine Tankstellen verf\xFCgbar</p>`;
  const sorted = prioritizeStations(stations, config.sort_mode, config.sort_fuel);
  const visible = Number.isInteger(config.visible_station_count) && (config.visible_station_count ?? 0) > 0 ? sorted.slice(0, config.visible_station_count) : sorted;
  const highlightIds = config.custom_layout === "highlights_list" ? new Set(sorted.slice(0, 2).map((station) => station.station_id)) : /* @__PURE__ */ new Set();
  const renderStation = (station, highlight = false) => {
    const prices = station.fuel_prices ? Object.entries(station.fuel_prices).map(([fuel, value]) => `${config.show_fuel_labels === false ? "" : `${fuel.toUpperCase()}: `}${value == null ? "\u2013" : `${value.toFixed(3)} \u20AC`}`).join(" \xB7 ") : station.price == null ? "\u2013" : `${station.price.toFixed(3)} \u20AC`;
    const price = config.show_prices === false ? "" : `<b class="prices">${prices}</b>`;
    const distance = config.show_distance === false ? "" : `<em>${station.distance_km == null ? "\u2013" : `${station.distance_km.toFixed(1)} km`}</em>`;
    const address = config.show_address === false ? "" : `<small>${escapeHtml(station.address ?? "")}</small>`;
    const status = config.show_status === false ? "" : `<span>${station.is_open === false ? "Geschlossen" : "Offen/unbekannt"}</span>`;
    const provider = config.show_provider_row === false || !station.provider ? "" : `<span>${escapeHtml(station.provider)}</span>`;
    const logoUrl = config.show_brand_logos !== false ? buildBrandLogoUrl(station.brand, config.logo_path) : null;
    const logo = logoUrl ? `<img class="brand-logo" src="${escapeHtml(logoUrl)}" alt="${escapeHtml(station.brand ?? "")} Logo" />` : `<span class="brand-logo-fallback" aria-hidden="true">\u26FD</span>`;
    const navigation = config.navigation !== false ? buildNavigationUrl(station.latitude, station.longitude, config.navigation_provider, station.name) : null;
    const navigate = navigation ? `<a class="navigate" href="${escapeHtml(navigation)}" target="_blank" rel="noopener noreferrer" aria-label="Navigieren">\u2197</a>` : "";
    const badge = config.show_badges !== false && highlight ? `<span class="badge">Highlight</span>` : "";
    return `<li class="fuel-station ${mode}${highlight ? " highlight" : ""}" data-station-id="${escapeHtml(station.station_id)}">${logo}<div class="station-main">${config.show_name === false ? "" : `<strong>${escapeHtml(station.name)}</strong>`}${badge}${address}<div class="meta">${status}${distance}${provider}</div></div>${price}${navigate}</li>`;
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
function renderRouteHtml(route, config) {
  if (route?.state === "error") return `<p class="route-error" role="alert">${escapeHtml(route.error ?? "Route konnte nicht berechnet werden.")}</p>`;
  if (!route || route.state !== "ready") return `<p class="route-empty" role="status">Keine berechnete Route vorhanden.</p>`;
  const distance = route.distance_m == null ? "\u2013" : `${(route.distance_m / 1e3).toFixed(1)} km`;
  const duration = route.duration_s == null ? "\u2013" : `${Math.round(route.duration_s / 60)} min`;
  const warnings = config.show_warnings === false ? "" : (route.warnings ?? []).map((warning) => `<li>${escapeHtml(warning)}</li>`).join("");
  const points = route.geometry ?? [];
  const map = points.length > 1 ? `<svg class="route-map" viewBox="0 0 320 120" role="img" aria-label="Routenverlauf"><polyline points="${points.map((point, index) => `${index / (points.length - 1) * 300 + 10},${110 - index % 2 * 45}`).join(" ")}" fill="none" stroke="var(--primary-color,#03a9f4)" stroke-width="5" stroke-linecap="round" /></svg>` : "";
  const tolls = route.metadata?.tolls;
  const tollText = tolls ? ` \xB7 Maut: ${tolls.total == null ? "unbekannt" : `${tolls.total.toFixed(2)} ${tolls.currency ?? "EUR"}`}${tolls.estimate ? " (Sch\xE4tzung)" : ""}` : "";
  return `${map}<p class="route-summary"><strong>${distance}</strong> \xB7 ${duration} \xB7 ${escapeHtml(route.provider ?? "unbekannt")}${tollText}</p>${warnings ? `<ul class="route-warnings">${warnings}</ul>` : ""}`;
}
function buildNavigationLink(origin, destination) {
  if (!destination || !Number.isFinite(destination.latitude) || !Number.isFinite(destination.longitude)) return null;
  const to = `${destination.latitude},${destination.longitude}`;
  const from = origin && Number.isFinite(origin.latitude) && Number.isFinite(origin.longitude) ? `${origin.latitude},${origin.longitude}` : "";
  if (typeof navigator !== "undefined" && /iPad|iPhone|iPod/.test(navigator.userAgent)) return `maps://?daddr=${encodeURIComponent(to)}${from ? `&saddr=${encodeURIComponent(from)}` : ""}`;
  if (typeof navigator !== "undefined" && /Android/.test(navigator.userAgent)) return `geo:${encodeURIComponent(to)}?q=${encodeURIComponent(to)}`;
  return `https://www.openstreetmap.org/directions?engine=fossgis_osrm_car&route=${encodeURIComponent(`${from ? `${from};` : ""}${to}`)}`;
}
function buildGpx(route, origin, destination, via, mode) {
  const point = (value, tag) => `<${tag} lat="${value.latitude}" lon="${value.longitude}" />`;
  const routePoints = [origin, ...via, destination];
  const routeXml = `<rte>${routePoints.map((value) => point(value, "rtept")).join("")}</rte>`;
  const geometry = route.geometry ?? [];
  const trackXml = `<trk><trkseg>${geometry.map((value) => point(value, "trkpt")).join("")}</trkseg></trk>`;
  const body = mode === "route" ? routeXml : mode === "track" ? trackXml : `${routeXml}${trackXml}`;
  return `<?xml version="1.0" encoding="UTF-8"?><gpx xmlns="http://www.topografix.com/GPX/1/1" version="1.1" creator="SmartCamper Suite"><metadata><name>SmartCamper Route</name></metadata>${body}</gpx>`;
}
function downloadGpx(route, origin, destination, via, mode) {
  const blob = new Blob([buildGpx(route, origin, destination, via, mode)], { type: "application/gpx+xml;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = `smartcamper-route-${mode}.gpx`;
  anchor.rel = "noopener";
  anchor.click();
  setTimeout(() => URL.revokeObjectURL(url), 0);
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
  routeVia = [];
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
      <label>Abrufmodus <select data-field="fetch_mode"><option value="automatic">Automatisch</option><option value="manual">Manuell</option></select></label>
      <label>Route Start (JSON) <input data-field="origin" placeholder='{"latitude":50,"longitude":8}' /></label>
      <label>Route Ziel (JSON) <input data-field="destination" placeholder='{"latitude":51,"longitude":9}' /></label>
      <label><input data-field="show_prices" type="checkbox" checked /> Preise</label>
      <label><input data-field="show_name" type="checkbox" checked /> Tankstellenname</label>
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
      const fetch_mode = editor.querySelector("[data-field=fetch_mode]").value;
      const visible_station_count = Number(editor.querySelector("[data-field=visible_station_count]").value) || 0;
      const parsePoint = (field) => {
        try {
          const value = JSON.parse(editor.querySelector(`[data-field=${field}]`).value);
          return value.latitude != null && value.longitude != null ? value : void 0;
        } catch {
          return void 0;
        }
      };
      const bool = (field) => editor.querySelector(`[data-field=${field}]`).checked;
      editor.dispatchEvent(new CustomEvent("config-changed", {
        bubbles: true,
        composed: true,
        detail: { config: { ...this.config, module, vehicle_id, origin: parsePoint("origin"), destination: parsePoint("destination"), display_mode, custom_layout, sort_mode, navigation_provider, fetch_mode, visible_station_count, navigation: true, show_prices: bool("show_prices"), show_name: bool("show_name"), show_distance: bool("show_distance"), show_address: bool("show_address"), show_status: bool("show_status"), show_brand_logos: bool("show_brand_logos"), show_diagnostics: bool("show_diagnostics"), show_refresh: bool("show_refresh") } }
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
    if (this.config.module === "route_planner") {
      const states2 = this._hass?.states ?? {};
      const vehicleId2 = selectVehicle(this.config, states2);
      const sensor2 = Object.values(states2).find((state) => state.attributes?.vehicle_id === vehicleId2 && state.attributes?.beta !== void 0);
      const route = sensor2?.attributes;
      const origin = route?.origin ?? route?.route_input?.origin ?? this.config.origin;
      const destination = route?.destination ?? route?.route_input?.destination ?? this.config.destination;
      const via = route?.via ?? route?.route_input?.via ?? this.routeVia;
      const calculate = origin && destination && vehicleId2 ? `<button class="route-calculate" type="button">Route berechnen</button>` : "";
      const pointEditor = (point, label, index) => point ? `<span class="route-point" data-index="${index ?? ""}"><b>${label}</b> ${point.latitude}, ${point.longitude}${index == null ? "" : ` <button class="route-up" type="button" data-index="${index}" aria-label="Zwischenstopp nach oben">\u2191</button><button class="route-down" type="button" data-index="${index}" aria-label="Zwischenstopp nach unten">\u2193</button><button class="route-remove" type="button" data-index="${index}" aria-label="Zwischenstopp entfernen">\xD7</button>`}</span>` : `<span class="route-point missing"><b>${label}</b> nicht gesetzt</span>`;
      const navigation = buildNavigationLink(origin, destination);
      const exportButtons = route?.state === "ready" && origin && destination ? `<div class="route-actions"><button class="route-gpx" data-mode="route" type="button">GPX-Route</button><button class="route-gpx" data-mode="track" type="button">GPX-Track</button><button class="route-gpx" data-mode="combined" type="button">GPX kombiniert</button>${navigation ? `<a class="route-navigation" href="${navigation}" target="_blank" rel="noopener">Im Navi \xF6ffnen</a>` : ""}</div>` : "";
      this.innerHTML = `<style>.route-card{font-family:var(--primary-font-family,sans-serif);padding:12px}.route-map{width:100%;height:120px;background:var(--secondary-background-color,#f4f7f9);border-radius:8px;cursor:crosshair}.route-warnings{padding-left:20px;color:var(--warning-color,#b26a00)}.route-error{color:var(--error-color,#d32f2f)}.route-calculate,.route-gpx,.route-actions a,.route-reset{border:1px solid var(--primary-color,#03a9f4);border-radius:999px;background:transparent;padding:6px 12px;color:inherit;text-decoration:none}.route-points{display:grid;gap:5px;margin:8px 0}.route-point{display:block}.route-point button{border:0;background:transparent;color:var(--error-color,#d32f2f);font-size:1.1rem}.route-actions{display:flex;gap:6px;flex-wrap:wrap;margin-top:8px}</style><article class="route-card"><header><strong>Camper Route Planner</strong><small>${vehicleId2 ?? "Kein Fahrzeug ausgew\xE4hlt"}</small></header><div class="route-points">${pointEditor(origin, "Start")}${via.map((point, index) => pointEditor(point, `Zwischenstopp ${index + 1}`, index)).join("")}${pointEditor(destination, "Ziel")}</div><button class="route-add" type="button">Zwischenstopp hinzuf\xFCgen</button> <button class="route-reset" type="button">Route zur\xFCcksetzen</button>${renderRouteHtml(route, this.config)}${exportButtons}${calculate}</article>`;
      this.querySelector(".route-add")?.addEventListener("click", () => {
        this.routeVia = [...via, { latitude: origin?.latitude ?? 0, longitude: origin?.longitude ?? 0 }];
        this.render();
      });
      this.querySelector(".route-map")?.addEventListener("click", (event) => {
        const geometry = route?.geometry ?? [];
        if (geometry.length < 2) return;
        const bounds = event.currentTarget.getBoundingClientRect();
        const x = Math.max(0, Math.min(1, event.clientX - bounds.left) / bounds.width);
        const y = Math.max(0, Math.min(1, event.clientY - bounds.top) / bounds.height);
        const latitudes = geometry.map((point) => point.latitude);
        const longitudes = geometry.map((point) => point.longitude);
        this.routeVia = [...via, {
          latitude: Math.min(...latitudes) + (1 - y) * (Math.max(...latitudes) - Math.min(...latitudes)),
          longitude: Math.min(...longitudes) + x * (Math.max(...longitudes) - Math.min(...longitudes)),
          label: "Karten-Zwischenstopp"
        }];
        this.render();
      });
      this.querySelectorAll(".route-remove").forEach((button) => button.addEventListener("click", () => {
        const removeIndex = Number(button.dataset.index);
        this.routeVia = via.filter((_point, index) => index !== removeIndex);
        this.render();
      }));
      const moveWaypoint = (button, delta) => {
        const index = Number(button.dataset.index);
        const nextIndex = index + delta;
        if (nextIndex < 0 || nextIndex >= via.length) return;
        const reordered = [...via];
        [reordered[index], reordered[nextIndex]] = [reordered[nextIndex], reordered[index]];
        this.routeVia = reordered;
        this.render();
      };
      this.querySelectorAll(".route-up").forEach((button) => button.addEventListener("click", () => moveWaypoint(button, -1)));
      this.querySelectorAll(".route-down").forEach((button) => button.addEventListener("click", () => moveWaypoint(button, 1)));
      this.querySelector(".route-reset")?.addEventListener("click", () => {
        this.routeVia = [];
        this.config = { ...this.config, origin: void 0, destination: void 0, via: [] };
        this.render();
      });
      this.querySelectorAll(".route-gpx").forEach((button) => button.addEventListener("click", () => {
        if (route && origin && destination) downloadGpx(route, origin, destination, via, button.dataset.mode);
      }));
      this.querySelector(".route-calculate")?.addEventListener("click", () => {
        if (vehicleId2 && origin && destination && this._hass?.callService) void this._hass.callService("smartcamper_suite", "calculate_route", { vehicle_id: vehicleId2, origin, destination, via });
      });
      return;
    }
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
    const radius = sensor?.attributes?.radius_km;
    const fuelTypes = Array.isArray(sensor?.attributes?.fuel_types) ? sensor.attributes.fuel_types.join(", ") : "";
    const provider = sensor?.attributes?.provider;
    const fetchMode = sensor?.attributes?.fetch_mode ?? this.config.fetch_mode;
    const usage = sensor?.attributes?.provider_usage;
    const usageText = usage ? Object.entries(usage).map(([provider2, value]) => `${provider2}: ${value.quotas?.cheap?.remaining ?? "?"} verbleibend`).join(" \xB7 ") : "";
    const diagnostics = this.config.show_diagnostics !== false && (sensor?.attributes?.error || usageText) ? `<p class="diagnostics" role="status">${sensor?.attributes?.error ? `Providerfehler: ${String(sensor.attributes.error)}` : ""}${usageText ? ` ${usageText}` : ""}</p>` : "";
    const lastUpdated = this.config.show_last_updated !== false && sensor?.attributes?.updated_at ? `<small class="updated">Stand: ${String(sensor.attributes.updated_at)}</small>` : "";
    const refresh = this.config.show_refresh !== false && fetchMode === "manual" ? `<button class="refresh" type="button">Jetzt aktualisieren</button>` : "";
    const headerDetails = [
      this.config.show_station_count === false ? "" : `${stations.length} Tankstellen`,
      this.config.show_radius === false || radius == null ? "" : `${radius} km`,
      this.config.show_fuel_type === false || !fuelTypes ? "" : fuelTypes,
      this.config.show_provider === false || !provider ? "" : `Quelle: ${provider}`,
      this.config.show_fetch_mode === false || !fetchMode ? "" : `Abruf: ${fetchMode}`
    ].filter(Boolean).join(" \xB7 ");
    const details = headerDetails ? `<small class="details">${headerDetails}</small>` : "";
    const dividerClass = this.config.show_dividers === false ? " no-dividers" : "";
    const densityClass = this.config.density === "compact" ? " dense" : "";
    this.innerHTML = `<style>.fuel-card{font-family:var(--primary-font-family, sans-serif);color:var(--primary-text-color,#263238);background:var(--ha-card-background,var(--card-background-color,#fff));padding:12px;border-radius:12px}.fuel-card header{display:flex;gap:8px;align-items:center;flex-wrap:wrap;margin-bottom:10px}.fuel-card header strong{font-size:1.1rem}.fuel-card header small,.updated,.details{opacity:.72}.fuel-card header small{margin-right:auto}.stations{list-style:none;margin:0;padding:0;display:grid;gap:8px}.fuel-station{display:grid;grid-template-columns:36px minmax(0,1fr) auto auto;gap:8px;align-items:center;padding:8px;border-bottom:1px solid var(--divider-color,#ddd)}.fuel-station.compact{padding:4px}.fuel-station.individual{border:1px solid var(--divider-color,#ddd);border-radius:8px}.fuel-station.highlight{background:color-mix(in srgb,var(--primary-color,#03a9f4) 12%,transparent)}.fuel-card.no-dividers .fuel-station{border-bottom:0}.fuel-card.dense{padding:6px}.brand-logo{width:32px;height:32px;object-fit:contain}.brand-logo-fallback{font-size:1.4rem}.station-main{min-width:0;display:grid;gap:2px}.station-main small,.meta{font-size:.85em;opacity:.78}.meta{display:flex;gap:8px;flex-wrap:wrap}.prices{white-space:nowrap}.navigate{font-size:1.35rem;text-decoration:none}.highlights{display:grid;gap:8px;margin-bottom:8px}.badge{margin-left:6px;font-size:.75em;color:var(--primary-color,#03a9f4)}.diagnostics{font-size:.85em;opacity:.8}.refresh{border:1px solid var(--primary-color,#03a9f4);border-radius:999px;background:transparent;padding:4px 10px}@media(max-width:500px){.fuel-station{grid-template-columns:30px minmax(0,1fr) auto}.fuel-station .prices{grid-column:2}.fuel-station .navigate{grid-column:3;grid-row:1 / span 2}}</style><article class="fuel-card${dividerClass}${densityClass}"><header>${this.config.show_title === false ? "" : "<strong>Tankstellen</strong>"}<small>${vehicleId ?? "Kein Fahrzeug ausgew\xE4hlt"}</small>${details}${lastUpdated}${refresh}</header>${diagnostics}<div>${stationHtml}</div></article>`;
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
