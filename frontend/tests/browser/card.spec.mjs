import assert from "node:assert/strict";
import { chromium } from "playwright";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";
import { existsSync } from "node:fs";

const here = dirname(fileURLToPath(import.meta.url));
const bundle = join(here, "..", "..", "..", "custom_components", "smartcamper_suite", "smartcamper-card.js");
const calls = [];
const hass = {
  states: {
    "sensor.womo_fuel_stations": {
      attributes: {
        vehicle_id: "womo", state: "ready", updated_at: "2026-10-22T09:00:00Z",
        stations: [
          { station_id: "near", name: "Near Fuel", brand: "Shell", distance_km: 2, address: "Main 1", is_open: true, latitude: 50, longitude: 8, fuel_prices: { diesel: 1.7, e5: null } },
          { station_id: "far", name: "Far Fuel", brand: "Aral", distance_km: 8, address: "Long Road", is_open: false, latitude: 50.1, longitude: 8.1, fuel_prices: { diesel: 1.6 } },
        ],
      },
    },
    "sensor.opel_fuel_stations": { attributes: { vehicle_id: "opel", state: "loading", stations: [] } },
  },
};

const executablePath = process.env.CHROMIUM_PATH ?? (existsSync("/usr/bin/chromium") ? "/usr/bin/chromium" : undefined);
const browser = await chromium.launch({ executablePath, headless: true, args: ["--no-sandbox"] });
try {
  const page = await browser.newPage({ viewport: { width: 390, height: 900 } });
  await page.exposeFunction("recordService", (...args) => calls.push(args));
  await page.setContent("<div id='root'></div>");
  await page.addScriptTag({ path: bundle });
  await page.evaluate(({ hass }) => {
    hass.callService = (...args) => window.recordService(...args);
    const root = document.querySelector("#root");
    const first = document.createElement("smartcamper-card");
    first.id = "first";
    first.setConfig({ type: "custom:smartcamper-card", module: "fuel_stations", vehicle_id: "womo", custom_layout: "highlights_list", sort_mode: "price", navigation_provider: "google", fetch_mode: "manual" });
    first.hass = hass;
    const second = document.createElement("smartcamper-card");
    second.id = "second";
    second.setConfig({ type: "custom:smartcamper-card", module: "fuel_stations", vehicle_id: "opel" });
    second.hass = hass;
    root.append(first, second);
  }, { hass });
  await page.locator("#first .fuel-station").first().waitFor();
  assert.equal(await page.locator("#first .fuel-station").count(), 2);
  assert.equal(await page.locator("#second .fuel-loading").count(), 1);
  assert.equal(await page.locator("#first .highlights").count(), 1);
  assert.match(await page.locator("#first").innerText(), /E5: –/);
  assert.match(await page.locator("#first").innerText(), /Far Fuel/);
  assert.equal(await page.locator("#first .brand-logo").count(), 2);
  assert.match((await page.locator("#first .brand-logo").allTextContents()).join(" ") + (await page.locator("#first .brand-logo").nth(1).getAttribute("src")), /shell\.png|aral\.png/);
  assert.match(await page.locator("#first .navigate").first().getAttribute("href"), /google\.com\/maps\/dir/);
  await page.locator("#first .refresh").click();
  assert.equal(calls.length, 1);
  assert.deepEqual(calls[0], ["smartcamper_suite", "refresh_fuel_stations", { vehicle_id: "womo" }]);

  const moduleText = await page.evaluate(() => {
    const card = document.querySelector("#first");
    card.setConfig({ type: "custom:smartcamper-card", module: "route_planner" });
    return card.textContent;
  });
  assert.match(moduleText, /vorbereitet/);

  const editorResult = await page.evaluate(() => {
    const card = document.createElement("smartcamper-card");
    document.body.append(card);
    const editor = card.getConfigElement();
    let detail;
    editor.addEventListener("config-changed", (event) => { detail = event.detail; });
    editor.querySelector("[data-field=sort_mode]").value = "price";
    editor.querySelector("[data-field=sort_mode]").dispatchEvent(new Event("change", { bubbles: true }));
    return detail.config.sort_mode;
  });
  assert.equal(editorResult, "price");
  console.log("browser card assertions: PASS");
} finally {
  await browser.close();
}
