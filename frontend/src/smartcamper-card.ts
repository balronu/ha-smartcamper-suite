import {
  type FuelStationView,
  type CardConfig,
  renderFuelStateHtml,
  selectVehicle,
  validateConfig,
} from "./config";

type HassState = { state?: string; attributes?: Record<string, unknown> };
type HassLike = { states?: Record<string, HassState>; callService?: (domain: string, service: string, data: Record<string, unknown>) => Promise<unknown> };

class SmartCamperCard extends HTMLElement {
  private config: CardConfig = { type: "custom:smartcamper-card", module: "travel_journal" };
  private _hass?: HassLike;

  setConfig(raw: CardConfig): void {
    this.config = validateConfig(raw);
    this.render();
  }

  set hass(value: HassLike) {
    this._hass = value;
    this.render();
  }

  get hass(): HassLike | undefined {
    return this._hass;
  }

  getConfigElement(): HTMLElement {
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
      <label><input data-field="show_prices" type="checkbox" checked /> Preise</label>
      <label><input data-field="show_distance" type="checkbox" checked /> Entfernung</label>
      <label><input data-field="show_address" type="checkbox" checked /> Adresse</label>
      <label><input data-field="show_status" type="checkbox" checked /> Status</label>
      <label><input data-field="show_brand_logos" type="checkbox" checked /> Anbieterlogos</label>
      <label><input data-field="show_diagnostics" type="checkbox" checked /> Diagnostik</label>
      <label><input data-field="show_refresh" type="checkbox" checked /> Aktualisieren</label>`;
    const emit = (): void => {
      const module = (editor.querySelector("[data-field=module]") as HTMLSelectElement).value;
      const vehicle_id = (editor.querySelector("[data-field=vehicle_id]") as HTMLInputElement).value || undefined;
      const sort_mode = (editor.querySelector("[data-field=sort_mode]") as HTMLSelectElement).value as "distance" | "price";
      const display_mode = (editor.querySelector("[data-field=display_mode]") as HTMLSelectElement).value as CardConfig["display_mode"];
      const custom_layout = (editor.querySelector("[data-field=custom_layout]") as HTMLSelectElement).value as CardConfig["custom_layout"];
      const navigation_provider = (editor.querySelector("[data-field=navigation_provider]") as HTMLSelectElement).value as CardConfig["navigation_provider"];
      const fetch_mode = (editor.querySelector("[data-field=fetch_mode]") as HTMLSelectElement).value as CardConfig["fetch_mode"];
      const visible_station_count = Number((editor.querySelector("[data-field=visible_station_count]") as HTMLInputElement).value) || 0;
      const bool = (field: string): boolean => (editor.querySelector(`[data-field=${field}]`) as HTMLInputElement).checked;
      editor.dispatchEvent(new CustomEvent("config-changed", {
        bubbles: true, composed: true, detail: { config: { ...this.config, module, vehicle_id, display_mode, custom_layout, sort_mode, navigation_provider, fetch_mode, visible_station_count, navigation: true, show_prices: bool("show_prices"), show_distance: bool("show_distance"), show_address: bool("show_address"), show_status: bool("show_status"), show_brand_logos: bool("show_brand_logos"), show_diagnostics: bool("show_diagnostics"), show_refresh: bool("show_refresh") } },
      }));
    };
    editor.querySelectorAll("select, input").forEach((element) => element.addEventListener("change", emit));
    return editor;
  }

  getStubConfig(): CardConfig {
    return { type: "custom:smartcamper-card", module: "fuel_stations" };
  }

  getCardSize(): number {
    return 4;
  }

  private render(): void {
    if (!this.isConnected && typeof document === "undefined") return;
    if (this.config.module !== "fuel_stations") {
      this.innerHTML = `<article><strong>SmartCamper Suite</strong><p>${this.config.module}</p><small>Modul ist vorbereitet.</small></article>`;
      return;
    }
    const states = this._hass?.states ?? {};
    const vehicleId = selectVehicle(this.config, states);
    const sensor = Object.values(states).find((state) => state.attributes?.vehicle_id === vehicleId);
    const status = sensor?.attributes?.state as string | undefined;
    const stations = this.mergeStations((sensor?.attributes?.stations ?? []) as FuelStationView[]);
    const stationHtml = renderFuelStateHtml(status, stations, this.config);
    const usage = sensor?.attributes?.provider_usage as Record<string, { quotas?: Record<string, { remaining?: number }> }> | undefined;
    const usageText = usage ? Object.entries(usage).map(([provider, value]) => `${provider}: ${value.quotas?.cheap?.remaining ?? "?"} verbleibend`).join(" · ") : "";
    const diagnostics = this.config.show_diagnostics !== false && (sensor?.attributes?.error || usageText)
      ? `<p class="diagnostics" role="status">${sensor?.attributes?.error ? `Providerfehler: ${String(sensor.attributes.error)}` : ""}${usageText ? ` ${usageText}` : ""}</p>` : "";
    const lastUpdated = this.config.show_last_updated !== false && sensor?.attributes?.updated_at
      ? `<small class="updated">Stand: ${String(sensor.attributes.updated_at)}</small>` : "";
    const refresh = this.config.show_refresh !== false && this.config.fetch_mode === "manual"
      ? `<button class="refresh" type="button">Jetzt aktualisieren</button>` : "";
    this.innerHTML = `<style>.fuel-card{font-family:var(--primary-font-family, sans-serif);color:var(--primary-text-color,#263238);background:var(--ha-card-background,var(--card-background-color,#fff));padding:12px;border-radius:12px}.fuel-card header{display:flex;gap:8px;align-items:center;flex-wrap:wrap;margin-bottom:10px}.fuel-card header strong{font-size:1.1rem}.fuel-card header small,.updated{opacity:.72}.fuel-card header small{margin-right:auto}.stations{list-style:none;margin:0;padding:0;display:grid;gap:8px}.fuel-station{display:grid;grid-template-columns:36px minmax(0,1fr) auto auto;gap:8px;align-items:center;padding:8px;border-bottom:1px solid var(--divider-color,#ddd)}.fuel-station.compact{padding:4px}.fuel-station.individual{border:1px solid var(--divider-color,#ddd);border-radius:8px}.fuel-station.highlight{background:color-mix(in srgb,var(--primary-color,#03a9f4) 12%,transparent)}.brand-logo{width:32px;height:32px;object-fit:contain}.brand-logo-fallback{font-size:1.4rem}.station-main{min-width:0;display:grid;gap:2px}.station-main small,.meta{font-size:.85em;opacity:.78}.meta{display:flex;gap:8px}.prices{white-space:nowrap}.navigate{font-size:1.35rem;text-decoration:none}.highlights{display:grid;gap:8px;margin-bottom:8px}.badge{margin-left:6px;font-size:.75em;color:var(--primary-color,#03a9f4)}.diagnostics{font-size:.85em;opacity:.8}.refresh{border:1px solid var(--primary-color,#03a9f4);border-radius:999px;background:transparent;padding:4px 10px}@media(max-width:500px){.fuel-station{grid-template-columns:30px minmax(0,1fr) auto}.fuel-station .prices{grid-column:2}.fuel-station .navigate{grid-column:3;grid-row:1 / span 2}}</style><article class="fuel-card"><header>${this.config.show_title === false ? "" : "<strong>Tankstellen</strong>"}<small>${vehicleId ?? "Kein Fahrzeug ausgewählt"}</small>${lastUpdated}${refresh}</header>${diagnostics}<div>${stationHtml}</div></article>`;
    this.querySelector(".refresh")?.addEventListener("click", () => {
      if (vehicleId && this._hass?.callService) void this._hass.callService("smartcamper_suite", "refresh_fuel_stations", { vehicle_id: vehicleId });
    });
  }

  private mergeStations(raw: FuelStationView[]): FuelStationView[] {
    const merged = new Map<string, FuelStationView>();
    for (const station of raw) {
      const current = merged.get(station.station_id);
      if (!current) { merged.set(station.station_id, { ...station, fuel_prices: station.fuel_type ? { [station.fuel_type]: station.price ?? null } : station.fuel_prices }); continue; }
      current.fuel_prices = { ...(current.fuel_prices ?? {}), ...(station.fuel_type ? { [station.fuel_type]: station.price ?? null } : station.fuel_prices ?? {}) };
    }
    return [...merged.values()];
  }
}

if (typeof window !== "undefined" && typeof customElements !== "undefined") {
  if (!customElements.get("smartcamper-card")) customElements.define("smartcamper-card", SmartCamperCard);
  const cards = (window as Window & { customCards?: Array<{ type: string }> }).customCards ?? [];
  if (!cards.some((card) => card.type === "smartcamper-card")) {
    cards.push({ type: "smartcamper-card" });
    (window as Window & { customCards?: Array<{ type: string }> }).customCards = cards;
  }
}
