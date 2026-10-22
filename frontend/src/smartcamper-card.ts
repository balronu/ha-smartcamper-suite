import { type CardConfig, validateConfig } from "./config";

class SmartCamperCard extends HTMLElement {
  setConfig(raw: CardConfig): void {
    const config = validateConfig(raw);
    this.innerHTML = `<article><strong>SmartCamper Suite</strong><p>${config.module}</p><small>Phase 2A development placeholder — no live data</small></article>`;
  }
  getCardSize(): number { return 2; }
}

if (typeof window !== "undefined" && typeof customElements !== "undefined") {
  if (!customElements.get("smartcamper-card")) customElements.define("smartcamper-card", SmartCamperCard);
  const cards = (window as Window & { customCards?: unknown[] }).customCards ?? [];
  if (!cards.some((card) => (card as { type?: string }).type === "smartcamper-card")) {
    cards.push({ type: "smartcamper-card", name: "SmartCamper Suite", description: "One module placeholder per card" });
    (window as Window & { customCards?: unknown[] }).customCards = cards;
  }
}
