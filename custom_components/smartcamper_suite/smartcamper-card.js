// src/config.ts
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
function renderFuelStationsHtml(stations, config) {
  const mode = config.display_mode ?? "detailed";
  if (!stations.length) return `<p class="fuel-empty">Keine Tankstellen verf\xFCgbar</p>`;
  const sorted = [...stations].sort((left, right) => {
    const leftValue = config.sort_mode === "price" ? left.price : left.distance_km;
    const rightValue = config.sort_mode === "price" ? right.price : right.distance_km;
    return (leftValue ?? Number.POSITIVE_INFINITY) - (rightValue ?? Number.POSITIVE_INFINITY);
  });
  const visible = Number.isInteger(config.visible_station_count) && (config.visible_station_count ?? 0) > 0 ? sorted.slice(0, config.visible_station_count) : sorted;
  return visible.map((station) => {
    const prices = station.fuel_prices ? Object.entries(station.fuel_prices).map(([fuel, value]) => `${fuel.toUpperCase()}: ${value == null ? "\u2013" : `${value.toFixed(3)} \u20AC`}`).join(" \xB7 ") : station.price == null ? "\u2013" : `${station.price.toFixed(3)} \u20AC`;
    const price = config.show_prices === false ? "" : `<b>${prices}</b>`;
    const distance = config.show_distance === false ? "" : `<em>${station.distance_km == null ? "\u2013" : `${station.distance_km.toFixed(1)} km`}</em>`;
    const address = config.show_address === false ? "" : `<small>${escapeHtml(station.address ?? "")}</small>`;
    const status = config.show_status === false ? "" : `<span>${station.is_open === false ? "Geschlossen" : "Offen/unbekannt"}</span>`;
    return `<li class="fuel-station ${mode}"><strong>${escapeHtml(station.name)}</strong>${price}${distance}${address}${status}</li>`;
  }).join("");
}
function renderFuelStateHtml(status, stations, config) {
  if (status === "loading") return '<p class="fuel-loading">Lade Tankstellen \u2026</p>';
  if (status === "error") return '<p class="fuel-error">Tankstellen konnten nicht geladen werden.</p>';
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
      <label>Sortierung <select data-field="sort_mode"><option value="distance">Entfernung</option><option value="price">Preis</option></select></label>
      <label>Anzahl <input data-field="visible_station_count" type="number" min="0" /></label>
      <label><input data-field="show_prices" type="checkbox" checked /> Preise</label>
      <label><input data-field="show_distance" type="checkbox" checked /> Entfernung</label>
      <label><input data-field="show_address" type="checkbox" checked /> Adresse</label>
      <label><input data-field="show_status" type="checkbox" checked /> Status</label>`;
    const emit = () => {
      const module = editor.querySelector("[data-field=module]").value;
      const vehicle_id = editor.querySelector("[data-field=vehicle_id]").value || void 0;
      const sort_mode = editor.querySelector("[data-field=sort_mode]").value;
      const visible_station_count = Number(editor.querySelector("[data-field=visible_station_count]").value) || 0;
      const bool = (field) => editor.querySelector(`[data-field=${field}]`).checked;
      editor.dispatchEvent(new CustomEvent("config-changed", {
        bubbles: true,
        composed: true,
        detail: { config: { ...this.config, module, vehicle_id, sort_mode, visible_station_count, show_prices: bool("show_prices"), show_distance: bool("show_distance"), show_address: bool("show_address"), show_status: bool("show_status") } }
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
    const stations = sensor?.attributes?.stations ?? [];
    const stationHtml = renderFuelStateHtml(status, stations, this.config);
    this.innerHTML = `<article class="fuel-card"><header><strong>Tankstellen</strong><small>${vehicleId ?? "Kein Fahrzeug ausgew\xE4hlt"}</small></header><div>${stationHtml}</div></article>`;
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
