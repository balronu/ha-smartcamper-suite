import {
  type FuelStationView,
  type CardConfig,
  renderFuelStateHtml,
  renderRouteHtml,
  renderJournalHtml,
  type RouteView,
  type RoutePoint,
  type JournalView,
  buildNavigationLink,
  downloadGpx,
  selectVehicle,
  validateConfig,
} from "./config";
import * as L from "leaflet";

type HassState = { state?: string; attributes?: Record<string, unknown> };
type HassLike = { states?: Record<string, HassState>; callService?: (domain: string, service: string, data: Record<string, unknown>) => Promise<unknown>; callWS?: (message: Record<string, unknown>) => Promise<any> };

class SmartCamperCard extends HTMLElement {
  private config: CardConfig = { type: "custom:smartcamper-card", module: "travel_journal" };
  private _hass?: HassLike;
  private routeVia: RoutePoint[] = [];
  private routeMap?: L.Map;
  private journalDetails?: JournalView;
  private journalDetailsVehicle?: string;
  private journalDetailsLoading = false;

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
    if (this.config.module === "travel_journal") {
      const states = this._hass?.states ?? {};
      const vehicleId = selectVehicle(this.config, states);
      const sensor = Object.values(states).find((state) => state.attributes?.vehicle_id === vehicleId && state.attributes?.database === "smartcamper_suite_travel_journal.sqlite");
      const journal = sensor?.attributes as JournalView | undefined;
      const view = journal && this.journalDetailsVehicle === vehicleId ? { ...journal, ...this.journalDetails } : journal;
      this.innerHTML = `<style>.journal-card{font-family:var(--primary-font-family,sans-serif);padding:12px;color:var(--primary-text-color,#263238)}.journal-card header{display:flex;gap:8px;align-items:center;margin-bottom:12px}.journal-card header small{margin-left:auto;opacity:.7}.journal-active{display:grid;gap:4px;padding:12px;border-radius:10px;background:var(--secondary-background-color,#f4f7f9)}.journal-active small,.journal-meta{opacity:.75}.journal-meta{display:block;margin-top:10px}.journal-actions,.journal-record-actions,.journal-drive-form{display:flex;gap:6px;flex-wrap:wrap;margin-top:12px}.journal-drives,.journal-suggestions{margin-top:12px}.journal-drives ul,.journal-suggestions ul{padding-left:18px}.journal-drive-form input{min-width:95px}.journal-create,.journal-pdf,.journal-gpx-label,.journal-drive-form button,.journal-record-actions button,.journal-drives button,.journal-suggestions button{border:1px solid var(--primary-color,#03a9f4);border-radius:999px;background:transparent;padding:6px 12px;color:inherit}.journal-gpx{display:none}</style>${renderJournalHtml(view, this.config)}`;
      void this.loadJournalDetails(vehicleId);
      this.querySelector(".journal-create")?.addEventListener("click", () => {
        if (vehicleId && this._hass?.callService) void this._hass.callService("smartcamper_suite", "journal_create_trip", { entry_id: "default", vehicle_id: vehicleId, title: "Neue Reise" });
      });
      const tripId = journal?.active_trip?.id;
      this.querySelector(".journal-edit")?.addEventListener("click", () => {
        if (tripId && vehicleId && this._hass?.callService) void this._hass.callService("smartcamper_suite", "journal_update_trip", { entry_id: "default", vehicle_id: vehicleId, trip_id: tripId, destination: "Bearbeitet" });
      });
      this.querySelector(".journal-complete")?.addEventListener("click", () => {
        if (tripId && vehicleId && this._hass?.callService) void this._hass.callService("smartcamper_suite", "journal_update_trip", { entry_id: "default", vehicle_id: vehicleId, trip_id: tripId, status: "completed" });
      });
      this.querySelector(".journal-delete")?.addEventListener("click", () => {
        if (tripId && vehicleId && this._hass?.callService) void this._hass.callService("smartcamper_suite", "journal_delete_trip", { entry_id: "default", vehicle_id: vehicleId, trip_id: tripId });
      });
      this.querySelector(".journal-pdf")?.addEventListener("click", async () => {
        if (!tripId || !vehicleId || !this._hass?.callWS) return;
        const result = await this._hass.callWS({ type: "smartcamper_suite/journal/export_pdf", vehicle_id: vehicleId, trip_id: tripId, language: "de" });
        if (!result?.pdf_base64) return;
        const bytes = Uint8Array.from(atob(result.pdf_base64), (value) => value.charCodeAt(0));
        const url = URL.createObjectURL(new Blob([bytes], { type: "application/pdf" }));
        const anchor = document.createElement("a"); anchor.href = url; anchor.download = result.filename ?? "smartcamper-travel-journal.pdf"; anchor.click(); URL.revokeObjectURL(url);
      });
      this.querySelector<HTMLInputElement>(".journal-gpx")?.addEventListener("change", async (event) => {
        const file = (event.target as HTMLInputElement).files?.[0];
        if (!file || !vehicleId || !this._hass?.callWS) return;
        const bytes = new Uint8Array(await file.arrayBuffer());
        const encoded = btoa(String.fromCharCode(...bytes));
        const digest = await crypto.subtle.digest("SHA-256", bytes);
        const file_hash = [...new Uint8Array(digest)].map((value) => value.toString(16).padStart(2, "0")).join("");
        await this._hass.callWS({ type: "smartcamper_suite/journal/import_gpx", vehicle_id: vehicleId, content_base64: encoded, file_hash });
      });
      this.querySelector<HTMLFormElement>(".journal-drive-form")?.addEventListener("submit", async (event) => {
        event.preventDefault();
        const form = event.currentTarget as HTMLFormElement;
        if (!vehicleId || !tripId || !this._hass?.callWS) return;
        const data = new FormData(form);
        await this._hass.callWS({ type: "smartcamper_suite/journal/create_manual_drive", vehicle_id: vehicleId, trip_id: tripId, occurred_at: String(data.get("occurred_at") ?? ""), start_location: String(data.get("start_location") ?? ""), end_location: String(data.get("end_location") ?? ""), distance_km: Number(data.get("distance_km") ?? 0) });
        this.journalDetails = undefined;
        this.journalDetailsVehicle = undefined;
        this.render();
      });
      this.querySelectorAll<HTMLButtonElement>(".journal-drive-link").forEach((button) => button.addEventListener("click", () => {
        if (vehicleId && tripId && this._hass?.callWS) void this._hass.callWS({ type: "smartcamper_suite/journal/link_drives", vehicle_id: vehicleId, trip_id: tripId, drive_ids: [button.dataset.driveId] });
      }));
      this.querySelectorAll<HTMLButtonElement>(".journal-drive-unlink").forEach((button) => button.addEventListener("click", () => {
        if (vehicleId && tripId && button.dataset.driveId && this._hass?.callWS) void this._hass.callWS({ type: "smartcamper_suite/journal/unlink_drive", vehicle_id: vehicleId, trip_id: tripId, drive_id: button.dataset.driveId });
      }));
      this.querySelectorAll<HTMLButtonElement>(".journal-drive-delete").forEach((button) => button.addEventListener("click", () => {
        if (vehicleId && button.dataset.driveId && this._hass?.callWS) void this._hass.callWS({ type: "smartcamper_suite/journal/delete_manual_drive", vehicle_id: vehicleId, drive_id: button.dataset.driveId });
      }));
      this.querySelector(".journal-route")?.addEventListener("click", () => {
        if (vehicleId && this._hass?.callWS) void this._hass.callWS({ type: "smartcamper_suite/journal/route", vehicle_id: vehicleId, trip_id: tripId });
      });
      this.querySelector(".journal-suggestions-generate")?.addEventListener("click", () => {
        if (vehicleId && this._hass?.callWS) void this._hass.callWS({ type: "smartcamper_suite/journal/generate_suggestions", vehicle_id: vehicleId, trip_id: tripId });
      });
      this.querySelectorAll<HTMLButtonElement>(".journal-suggestion-accept").forEach((button) => button.addEventListener("click", () => {
        if (vehicleId && button.dataset.suggestionId && this._hass?.callWS) void this._hass.callWS({ type: "smartcamper_suite/journal/accept_suggestion", vehicle_id: vehicleId, suggestion_id: button.dataset.suggestionId, trip_id: tripId });
      }));
      this.querySelectorAll<HTMLButtonElement>(".journal-suggestion-dismiss").forEach((button) => button.addEventListener("click", () => {
        if (vehicleId && button.dataset.suggestionId && this._hass?.callWS) void this._hass.callWS({ type: "smartcamper_suite/journal/dismiss_suggestion", vehicle_id: vehicleId, suggestion_id: button.dataset.suggestionId });
      }));
      this.querySelector(".journal-stop-create")?.addEventListener("click", () => {
        if (vehicleId && this._hass?.callWS) void this._hass.callWS({ type: "smartcamper_suite/journal/create_stop", vehicle_id: vehicleId, trip_id: tripId, name: "Neuer Stopp", occurred_at: new Date().toISOString() });
      });
      this.querySelector(".journal-stay-create")?.addEventListener("click", () => {
        if (vehicleId && this._hass?.callWS) void this._hass.callWS({ type: "smartcamper_suite/journal/create_stay", vehicle_id: vehicleId, trip_id: tripId, name: "Neuer Aufenthalt" });
      });
      this.querySelectorAll<HTMLButtonElement>(".journal-stay-edit").forEach((button) => button.addEventListener("click", () => {
        if (vehicleId && button.dataset.stayId && this._hass?.callWS) void this._hass.callWS({ type: "smartcamper_suite/journal/update_stay", vehicle_id: vehicleId, stay_id: button.dataset.stayId, name: "Bearbeiteter Aufenthalt" });
      }));
      this.querySelectorAll<HTMLButtonElement>(".journal-stay-delete").forEach((button) => button.addEventListener("click", () => {
        if (vehicleId && button.dataset.stayId && this._hass?.callWS) void this._hass.callWS({ type: "smartcamper_suite/journal/delete_stay", vehicle_id: vehicleId, stay_id: button.dataset.stayId });
      }));
      this.querySelector(".journal-expense-create")?.addEventListener("click", () => {
        if (vehicleId && this._hass?.callWS) void this._hass.callWS({ type: "smartcamper_suite/journal/create_expense", vehicle_id: vehicleId, trip_id: tripId, category: "other", amount_minor: 0, currency: "EUR" });
      });
      this.querySelector(".journal-diagnostics")?.addEventListener("click", () => {
        if (vehicleId && this._hass?.callWS) void this._hass.callWS({ type: "smartcamper_suite/journal/diagnostics", vehicle_id: vehicleId });
      });
      this.querySelectorAll<HTMLButtonElement>(".journal-stop-delete").forEach((button) => button.addEventListener("click", () => {
        if (vehicleId && button.dataset.stopId && this._hass?.callWS) void this._hass.callWS({ type: "smartcamper_suite/journal/delete_stop", vehicle_id: vehicleId, stop_id: button.dataset.stopId });
      }));
      this.querySelectorAll<HTMLButtonElement>(".journal-expense-delete").forEach((button) => button.addEventListener("click", () => {
        if (vehicleId && button.dataset.expenseId && this._hass?.callWS) void this._hass.callWS({ type: "smartcamper_suite/journal/delete_expense", vehicle_id: vehicleId, expense_id: button.dataset.expenseId });
      }));
      this.querySelectorAll<HTMLButtonElement>(".journal-expense-edit").forEach((button) => button.addEventListener("click", () => {
        if (vehicleId && button.dataset.expenseId && this._hass?.callWS) void this._hass.callWS({ type: "smartcamper_suite/journal/update_expense", vehicle_id: vehicleId, expense_id: button.dataset.expenseId, note: "Bearbeitet" });
      }));
      this.querySelectorAll<HTMLButtonElement>(".journal-rating-edit").forEach((button) => button.addEventListener("click", () => {
        if (vehicleId && button.dataset.placeId && this._hass?.callWS) void this._hass.callWS({ type: "smartcamper_suite/journal/upsert_rating", vehicle_id: vehicleId, place_id: button.dataset.placeId, overall: 5 });
      }));
      this.querySelectorAll<HTMLButtonElement>(".journal-overnight-edit").forEach((button) => button.addEventListener("click", () => {
        if (vehicleId && button.dataset.placeId && this._hass?.callWS) void this._hass.callWS({ type: "smartcamper_suite/journal/upsert_overnight", vehicle_id: vehicleId, place_id: button.dataset.placeId, place_kind: "campsite" });
      }));
      this.querySelectorAll<HTMLButtonElement>(".journal-interruption-assign").forEach((button) => button.addEventListener("click", () => {
        if (vehicleId && tripId && button.dataset.interruptionId && this._hass?.callWS) void this._hass.callWS({ type: "smartcamper_suite/journal/assign_interruption", vehicle_id: vehicleId, trip_id: tripId, interruption_id: button.dataset.interruptionId, status: "assigned" });
      }));
      return;
    }
    if (this.config.module === "route_planner") {
      this.routeMap?.remove();
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
      this.innerHTML = `<style>.route-card{font-family:var(--primary-font-family,sans-serif);padding:12px}.route-leaflet-map{width:100%;height:180px;background:var(--secondary-background-color,#f4f7f9);border-radius:8px;margin-bottom:8px}.route-map{width:100%;height:120px;background:var(--secondary-background-color,#f4f7f9);border-radius:8px;cursor:crosshair}.route-warnings{padding-left:20px;color:var(--warning-color,#b26a00)}.route-error{color:var(--error-color,#d32f2f)}.route-calculate,.route-gpx,.route-actions a,.route-reset{border:1px solid var(--primary-color,#03a9f4);border-radius:999px;background:transparent;padding:6px 12px;color:inherit;text-decoration:none}.route-points{display:grid;gap:5px;margin:8px 0}.route-point{display:block}.route-point button{border:0;background:transparent;color:var(--error-color,#d32f2f);font-size:1.1rem}.route-actions{display:flex;gap:6px;flex-wrap:wrap;margin-top:8px}</style><article class="route-card"><header><strong>Camper Route Planner</strong><small>${vehicleId ?? "Kein Fahrzeug ausgewählt"}</small></header><div class="route-points">${pointEditor(origin, "Start")}${via.map((point, index) => pointEditor(point, `Zwischenstopp ${index + 1}`, index)).join("")}${pointEditor(destination, "Ziel")}</div><button class="route-add" type="button">Zwischenstopp hinzufügen</button> <button class="route-reset" type="button">Route zurücksetzen</button>${renderRouteHtml(route, this.config)}${exportButtons}${calculate}</article>`;
      this.querySelector(".route-add")?.addEventListener("click", () => {
        this.routeVia = [...via, { latitude: origin?.latitude ?? 0, longitude: origin?.longitude ?? 0 }];
        this.render();
      });
      const leafletHost = this.querySelector<HTMLElement>(".route-leaflet-map");
      if (leafletHost && route?.geometry && route.geometry.length > 1) {
        try {
          this.routeMap = L.map(leafletHost, { zoomControl: false, attributionControl: false });
          const line = route.geometry.map((point) => [point.latitude, point.longitude] as [number, number]);
          this.routeMap.fitBounds(line, { padding: [10, 10] });
          L.polyline(line, { color: "#03a9f4", weight: 5 }).addTo(this.routeMap);
          window.setTimeout(() => this.routeMap?.invalidateSize(), 0);
        } catch {
          this.routeMap = undefined;
        }
      }
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

  private async loadJournalDetails(vehicleId: string | undefined): Promise<void> {
    if (!vehicleId || !this._hass?.callWS || this.journalDetailsLoading || this.journalDetailsVehicle === vehicleId) return;
    this.journalDetailsLoading = true;
    try {
      const details = await this._hass.callWS({ type: "smartcamper_suite/journal/list", vehicle_id: vehicleId });
      this.journalDetails = { vehicle_id: vehicleId, drives: details?.drives ?? [], suggestions: details?.suggestions ?? [], stays: details?.stays ?? [], stops: details?.stops ?? [], expenses: details?.expenses ?? [], ratings: details?.ratings ?? [], overnights: details?.overnights ?? [], interruptions: details?.interruptions ?? [] };
      this.journalDetailsVehicle = vehicleId;
      this.render();
    } catch {
      this.journalDetails = { vehicle_id: vehicleId, drives: [], suggestions: [] };
      this.journalDetailsVehicle = vehicleId;
    } finally {
      this.journalDetailsLoading = false;
    }
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
