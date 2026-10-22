import {
  type FuelStationView,
  type CardConfig,
  renderFuelStateHtml,
  renderRouteHtml,
  type RouteView,
  type RoutePoint,
  buildNavigationLink,
  downloadGpx,
  selectVehicle,
  validateConfig,
} from "./config";

type HassState = { state?: string; attributes?: Record<string, unknown> };
type HassLike = { states?: Record<string, HassState>; callService?: (domain: string, service: string, data: Record<string, unknown>) => Promise<unknown> };

class SmartCamperCard extends HTMLElement {
  private config: CardConfig = { type: "custom:smartcamper-card", module: "travel_journal" };
  private _hass?: HassLike;
  private routeVia: RoutePoint[] = [];

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
    const emit = (): void => {
      const module = (editor.querySelector("[data-field=module]") as HTMLSelectElement).value;
      const vehicle_id = (editor.querySelector("[data-field=vehicle_id]") as HTMLInputElement).value || undefined;
      const sort_mode = (editor.querySelector("[data-field=sort_mode]") as HTMLSelectElement).value as "distance" | "price";
      const display_mode = (editor.querySelector("[data-field=display_mode]") as HTMLSelectElement).value as CardConfig["display_mode"];
      const custom_layout = (editor.querySelector("[data-field=custom_layout]") as HTMLSelectElement).value as CardConfig["custom_layout"];
      const navigation_provider = (editor.querySelector("[data-field=navigation_provider]") as HTMLSelectElement).value as CardConfig["navigation_provider"];
      const fetch_mode = (editor.querySelector("[data-field=fetch_mode]") as HTMLSelectElement).value as CardConfig["fetch_mode"];
      const visible_station_count = Number((editor.querySelector("[data-field=visible_station_count]") as HTMLInputElement).value) || 0;
      const parsePoint = (field: string): { latitude: number; longitude: number } | undefined => {
        try { const value = JSON.parse((editor.querySelector(`[data-field=${field}]`) as HTMLInputElement).value); return value.latitude != null && value.longitude != null ? value : undefined; } catch { return undefined; }
      };
      const bool = (field: string): boolean => (editor.querySelector(`[data-field=${field}]`) as HTMLInputElement).checked;
      editor.dispatchEvent(new CustomEvent("config-changed", {
        bubbles: true, composed: true, detail: { config: { ...this.config, module, vehicle_id, origin: parsePoint("origin"), destination: parsePoint("destination"), display_mode, custom_layout, sort_mode, navigation_provider, fetch_mode, visible_station_count, navigation: true, show_prices: bool("show_prices"), show_name: bool("show_name"), show_distance: bool("show_distance"), show_address: bool("show_address"), show_status: bool("show_status"), show_brand_logos: bool("show_brand_logos"), show_diagnostics: bool("show_diagnostics"), show_refresh: bool("show_refresh") } },
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
    if (this.config.module === "route_planner") {
      const states = this._hass?.states ?? {};
      const vehicleId = selectVehicle(this.config, states);
      const sensor = Object.values(states).find((state) => state.attributes?.vehicle_id === vehicleId && state.attributes?.beta !== undefined);
      const route = sensor?.attributes as RouteView | undefined;
      const origin = route?.origin ?? route?.route_input?.origin ?? this.config.origin;
      const destination = route?.destination ?? route?.route_input?.destination ?? this.config.destination;
      const via = route?.via ?? route?.route_input?.via ?? this.routeVia;
      const calculate = origin && destination && vehicleId
        ? `<button class="route-calculate" type="button">Route berechnen</button>` : "";
      const pointEditor = (point: RoutePoint | undefined, label: string, index?: number): string => point
        ? `<span class="route-point" data-index="${index ?? ""}"><b>${label}</b> ${point.latitude}, ${point.longitude}${index == null ? "" : ` <button class="route-up" type="button" data-index="${index}" aria-label="Zwischenstopp nach oben">↑</button><button class="route-down" type="button" data-index="${index}" aria-label="Zwischenstopp nach unten">↓</button><button class="route-remove" type="button" data-index="${index}" aria-label="Zwischenstopp entfernen">×</button>`}</span>`
        : `<span class="route-point missing"><b>${label}</b> nicht gesetzt</span>`;
      const navigation = buildNavigationLink(origin, destination);
      const exportButtons = route?.state === "ready" && origin && destination
        ? `<div class="route-actions"><button class="route-gpx" data-mode="route" type="button">GPX-Route</button><button class="route-gpx" data-mode="track" type="button">GPX-Track</button><button class="route-gpx" data-mode="combined" type="button">GPX kombiniert</button>${navigation ? `<a class="route-navigation" href="${navigation}" target="_blank" rel="noopener">Im Navi öffnen</a>` : ""}</div>` : "";
      this.innerHTML = `<style>.route-card{font-family:var(--primary-font-family,sans-serif);padding:12px}.route-map{width:100%;height:120px;background:var(--secondary-background-color,#f4f7f9);border-radius:8px;cursor:crosshair}.route-warnings{padding-left:20px;color:var(--warning-color,#b26a00)}.route-error{color:var(--error-color,#d32f2f)}.route-calculate,.route-gpx,.route-actions a,.route-reset{border:1px solid var(--primary-color,#03a9f4);border-radius:999px;background:transparent;padding:6px 12px;color:inherit;text-decoration:none}.route-points{display:grid;gap:5px;margin:8px 0}.route-point{display:block}.route-point button{border:0;background:transparent;color:var(--error-color,#d32f2f);font-size:1.1rem}.route-actions{display:flex;gap:6px;flex-wrap:wrap;margin-top:8px}</style><article class="route-card"><header><strong>Camper Route Planner</strong><small>${vehicleId ?? "Kein Fahrzeug ausgewählt"}</small></header><div class="route-points">${pointEditor(origin, "Start")}${via.map((point, index) => pointEditor(point, `Zwischenstopp ${index + 1}`, index)).join("")}${pointEditor(destination, "Ziel")}</div><button class="route-add" type="button">Zwischenstopp hinzufügen</button> <button class="route-reset" type="button">Route zurücksetzen</button>${renderRouteHtml(route, this.config)}${exportButtons}${calculate}</article>`;
      this.querySelector(".route-add")?.addEventListener("click", () => {
        this.routeVia = [...via, { latitude: origin?.latitude ?? 0, longitude: origin?.longitude ?? 0 }];
        this.render();
      });
      this.querySelector(".route-map")?.addEventListener("click", (event) => {
        const geometry = route?.geometry ?? [];
        if (geometry.length < 2) return;
        const bounds = (event.currentTarget as SVGElement).getBoundingClientRect();
        const x = Math.max(0, Math.min(1, (event as MouseEvent).clientX - bounds.left) / bounds.width);
        const y = Math.max(0, Math.min(1, (event as MouseEvent).clientY - bounds.top) / bounds.height);
        const latitudes = geometry.map((point) => point.latitude);
        const longitudes = geometry.map((point) => point.longitude);
        this.routeVia = [...via, {
          latitude: Math.min(...latitudes) + (1 - y) * (Math.max(...latitudes) - Math.min(...latitudes)),
          longitude: Math.min(...longitudes) + x * (Math.max(...longitudes) - Math.min(...longitudes)),
          label: "Karten-Zwischenstopp",
        }];
        this.render();
      });
      this.querySelectorAll<HTMLButtonElement>(".route-remove").forEach((button) => button.addEventListener("click", () => {
        const removeIndex = Number(button.dataset.index);
        this.routeVia = via.filter((_point, index) => index !== removeIndex);
        this.render();
      }));
      const moveWaypoint = (button: HTMLButtonElement, delta: number): void => {
        const index = Number(button.dataset.index);
        const nextIndex = index + delta;
        if (nextIndex < 0 || nextIndex >= via.length) return;
        const reordered = [...via];
        [reordered[index], reordered[nextIndex]] = [reordered[nextIndex], reordered[index]];
        this.routeVia = reordered;
        this.render();
      };
      this.querySelectorAll<HTMLButtonElement>(".route-up").forEach((button) => button.addEventListener("click", () => moveWaypoint(button, -1)));
      this.querySelectorAll<HTMLButtonElement>(".route-down").forEach((button) => button.addEventListener("click", () => moveWaypoint(button, 1)));
      this.querySelector(".route-reset")?.addEventListener("click", () => {
        this.routeVia = [];
        this.config = { ...this.config, origin: undefined, destination: undefined, via: [] };
        this.render();
      });
      this.querySelectorAll<HTMLButtonElement>(".route-gpx").forEach((button) => button.addEventListener("click", () => {
        if (route && origin && destination) downloadGpx(route, origin, destination, via, button.dataset.mode as "route" | "track" | "combined");
      }));
      this.querySelector(".route-calculate")?.addEventListener("click", () => {
        if (vehicleId && origin && destination && this._hass?.callService) void this._hass.callService("smartcamper_suite", "calculate_route", { vehicle_id: vehicleId, origin, destination, via });
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
    const status = sensor?.attributes?.state as string | undefined;
    const stations = this.mergeStations((sensor?.attributes?.stations ?? []) as FuelStationView[]);
    const stationHtml = renderFuelStateHtml(status, stations, this.config);
    const radius = sensor?.attributes?.radius_km;
    const fuelTypes = Array.isArray(sensor?.attributes?.fuel_types) ? sensor.attributes.fuel_types.join(", ") : "";
    const provider = sensor?.attributes?.provider as string | undefined;
    const fetchMode = (sensor?.attributes?.fetch_mode as string | undefined) ?? this.config.fetch_mode;
    const usage = sensor?.attributes?.provider_usage as Record<string, { quotas?: Record<string, { remaining?: number }> }> | undefined;
    const usageText = usage ? Object.entries(usage).map(([provider, value]) => `${provider}: ${value.quotas?.cheap?.remaining ?? "?"} verbleibend`).join(" · ") : "";
    const diagnostics = this.config.show_diagnostics !== false && (sensor?.attributes?.error || usageText)
      ? `<p class="diagnostics" role="status">${sensor?.attributes?.error ? `Providerfehler: ${String(sensor.attributes.error)}` : ""}${usageText ? ` ${usageText}` : ""}</p>` : "";
    const lastUpdated = this.config.show_last_updated !== false && sensor?.attributes?.updated_at
      ? `<small class="updated">Stand: ${String(sensor.attributes.updated_at)}</small>` : "";
    const refresh = this.config.show_refresh !== false && fetchMode === "manual"
      ? `<button class="refresh" type="button">Jetzt aktualisieren</button>` : "";
    const headerDetails = [
      this.config.show_station_count === false ? "" : `${stations.length} Tankstellen`,
      this.config.show_radius === false || radius == null ? "" : `${radius} km`,
      this.config.show_fuel_type === false || !fuelTypes ? "" : fuelTypes,
      this.config.show_provider === false || !provider ? "" : `Quelle: ${provider}`,
      this.config.show_fetch_mode === false || !fetchMode ? "" : `Abruf: ${fetchMode}`,
    ].filter(Boolean).join(" · ");
    const details = headerDetails ? `<small class="details">${headerDetails}</small>` : "";
    const dividerClass = this.config.show_dividers === false ? " no-dividers" : "";
    const densityClass = this.config.density === "compact" ? " dense" : "";
    this.innerHTML = `<style>.fuel-card{font-family:var(--primary-font-family, sans-serif);color:var(--primary-text-color,#263238);background:var(--ha-card-background,var(--card-background-color,#fff));padding:12px;border-radius:12px}.fuel-card header{display:flex;gap:8px;align-items:center;flex-wrap:wrap;margin-bottom:10px}.fuel-card header strong{font-size:1.1rem}.fuel-card header small,.updated,.details{opacity:.72}.fuel-card header small{margin-right:auto}.stations{list-style:none;margin:0;padding:0;display:grid;gap:8px}.fuel-station{display:grid;grid-template-columns:36px minmax(0,1fr) auto auto;gap:8px;align-items:center;padding:8px;border-bottom:1px solid var(--divider-color,#ddd)}.fuel-station.compact{padding:4px}.fuel-station.individual{border:1px solid var(--divider-color,#ddd);border-radius:8px}.fuel-station.highlight{background:color-mix(in srgb,var(--primary-color,#03a9f4) 12%,transparent)}.fuel-card.no-dividers .fuel-station{border-bottom:0}.fuel-card.dense{padding:6px}.brand-logo{width:32px;height:32px;object-fit:contain}.brand-logo-fallback{font-size:1.4rem}.station-main{min-width:0;display:grid;gap:2px}.station-main small,.meta{font-size:.85em;opacity:.78}.meta{display:flex;gap:8px;flex-wrap:wrap}.prices{white-space:nowrap}.navigate{font-size:1.35rem;text-decoration:none}.highlights{display:grid;gap:8px;margin-bottom:8px}.badge{margin-left:6px;font-size:.75em;color:var(--primary-color,#03a9f4)}.diagnostics{font-size:.85em;opacity:.8}.refresh{border:1px solid var(--primary-color,#03a9f4);border-radius:999px;background:transparent;padding:4px 10px}@media(max-width:500px){.fuel-station{grid-template-columns:30px minmax(0,1fr) auto}.fuel-station .prices{grid-column:2}.fuel-station .navigate{grid-column:3;grid-row:1 / span 2}}</style><article class="fuel-card${dividerClass}${densityClass}"><header>${this.config.show_title === false ? "" : "<strong>Tankstellen</strong>"}<small>${vehicleId ?? "Kein Fahrzeug ausgewählt"}</small>${details}${lastUpdated}${refresh}</header>${diagnostics}<div>${stationHtml}</div></article>`;
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
