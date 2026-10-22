// src/config.ts
var MODULES = /* @__PURE__ */ new Set(["travel_journal", "fuel_stations", "route_planner", "border_forecast"]);
function validateConfig(config) {
  if (!MODULES.has(config.module)) throw new Error("Unknown SmartCamper module");
  return config;
}

// src/smartcamper-card.ts
var SmartCamperCard = class extends HTMLElement {
  setConfig(raw) {
    const config = validateConfig(raw);
    this.innerHTML = `<article><strong>SmartCamper Suite</strong><p>${config.module}</p><small>Phase 2A development placeholder \u2014 no live data</small></article>`;
  }
  getCardSize() {
    return 2;
  }
};
if (typeof window !== "undefined" && typeof customElements !== "undefined") {
  if (!customElements.get("smartcamper-card")) customElements.define("smartcamper-card", SmartCamperCard);
  const cards = window.customCards ?? [];
  if (!cards.some((card) => card.type === "smartcamper-card")) {
    cards.push({ type: "smartcamper-card", name: "SmartCamper Suite", description: "One module placeholder per card" });
    window.customCards = cards;
  }
}
