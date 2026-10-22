import {
  type CardConfig,
  renderFuelStationsHtml,
  selectVehicle,
  validateConfig,
} from "./config";

type HassState = { state?: string; attributes?: Record<string, unknown> };
type HassLike = { states?: Record<string, HassState> };

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
      <label>Fahrzeug <input data-field="vehicle_id" placeholder="Fahrzeug-ID (optional)" /></label>`;
    const emit = (): void => {
      const module = (editor.querySelector("[data-field=module]") as HTMLSelectElement).value;
      const vehicle_id = (editor.querySelector("[data-field=vehicle_id]") as HTMLInputElement).value || undefined;
      editor.dispatchEvent(new CustomEvent("config-changed", {
        bubbles: true, composed: true, detail: { config: { ...this.config, module, vehicle_id } },
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
    const stations = (sensor?.attributes?.stations ?? []) as Parameters<typeof renderFuelStationsHtml>[0];
    this.innerHTML = `<article class="fuel-card"><header><strong>Tankstellen</strong><small>${vehicleId ?? "Kein Fahrzeug ausgewählt"}</small></header><ul>${renderFuelStationsHtml(stations, this.config)}</ul></article>`;
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
