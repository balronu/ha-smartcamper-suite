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
    "sensor.womo_route": { attributes: { vehicle_id: "womo", state: "ready", beta: true, provider: "nakordoni_motorhome", distance_m: 123456, duration_s: 7200, geometry: [{ latitude: 50, longitude: 8 }, { latitude: 50.5, longitude: 8.5 }, { latitude: 51, longitude: 9 }], warnings: ["Motorhome-Routing ist Beta"] } },
    "sensor.womo_travel_journal": { attributes: { vehicle_id: "womo", database: "smartcamper_suite_travel_journal.sqlite", trip_count: 2, active_trip_count: 1, active_trip: { id: "trip_1", title: "Alpenfahrt", destination: "Tirol", status: "active" }, expense_total_minor: 12345, gps_point_count: 18 } },
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
  for (const mode of ["compact", "detailed", "individual"]) {
    await page.evaluate((mode) => document.querySelector("#first").setConfig({ type: "custom:smartcamper-card", module: "fuel_stations", vehicle_id: "womo", display_mode: mode }), mode);
    assert.equal(await page.locator(`#first .fuel-station.${mode}`).count(), 2);
  }
  await page.evaluate(() => document.querySelector("#first").setConfig({ type: "custom:smartcamper-card", module: "fuel_stations", vehicle_id: "womo", custom_layout: "highlights_list", sort_mode: "price", navigation_provider: "google", fetch_mode: "manual" }));
  await page.locator("#first .refresh").click();
  assert.equal(calls.length, 1);
  assert.deepEqual(calls[0], ["smartcamper_suite", "refresh_fuel_stations", { vehicle_id: "womo" }]);

  const moduleText = await page.evaluate(() => {
    const card = document.querySelector("#first");
    card.setConfig({ type: "custom:smartcamper-card", module: "route_planner" });
    return card.textContent;
  });
  assert.match(moduleText, /Camper Route Planner/);

  const editorResult = await page.evaluate(() => {
    const card = document.createElement("smartcamper-card");
    document.body.append(card);
    const editor = card.getConfigElement();
    let detail;
    editor.addEventListener("config-changed", (event) => { detail = event.detail; });
    editor.querySelector("[data-field=sort_mode]").value = "price";
    editor.querySelector("[data-field=sort_mode]").dispatchEvent(new Event("change", { bubbles: true }));
    editor.querySelector("[data-field=fetch_mode]").value = "manual";
    editor.querySelector("[data-field=fetch_mode]").dispatchEvent(new Event("change", { bubbles: true }));
    return { sort: detail.config.sort_mode, fetch: detail.config.fetch_mode };
  });
  assert.deepEqual(editorResult, { sort: "price", fetch: "manual" });
  await page.evaluate(() => document.querySelector("#first").setConfig({ type: "custom:smartcamper-card", module: "route_planner", vehicle_id: "womo", origin: { latitude: 50, longitude: 8 }, destination: { latitude: 51, longitude: 9 } }));
  assert.equal(await page.locator("#first .route-map").count(), 1);
  assert.match(await page.locator("#first").innerText(), /123\.5 km/);
  assert.match(await page.locator("#first").innerText(), /Beta/);
  assert.equal(await page.locator("#first .route-navigation").count(), 1);
  await page.locator("#first .route-add").click();
  assert.equal(await page.locator("#first .route-remove").count(), 1);
  await page.locator("#first .route-remove").click();
  await page.locator("#first .route-map").click({ position: { x: 160, y: 60 } });
  assert.equal(await page.locator("#first .route-remove").count(), 1);
  await page.locator("#first .route-remove").click();
  const download = await Promise.all([
    page.waitForEvent("download"),
    page.locator("#first .route-gpx[data-mode=combined]").click(),
  ]);
  assert.match(download[0].suggestedFilename(), /smartcamper-route-combined\.gpx/);
  await page.locator("#first .route-calculate").click();
  assert.deepEqual(calls.at(-1), ["smartcamper_suite", "calculate_route", { vehicle_id: "womo", origin: { latitude: 50, longitude: 8 }, destination: { latitude: 51, longitude: 9 }, via: [] }]);
  await page.evaluate(() => document.querySelector("#first").setConfig({ type: "custom:smartcamper-card", module: "travel_journal", vehicle_id: "womo" }));
  assert.match(await page.locator("#first").innerText(), /Alpenfahrt/);
  assert.match(await page.locator("#first").innerText(), /2 Reisen/);
  await page.locator("#first .journal-create").click();
  assert.deepEqual(calls.at(-1), ["smartcamper_suite", "journal_create_trip", { entry_id: "default", vehicle_id: "womo", title: "Neue Reise" }]);
  await page.evaluate(() => {
    document.querySelector("#first").hass.callWS = async () => ({ pdf_base64: "JVBERi0xLjQKJSVFT0YK", filename: "journal.pdf" });
  });
  const journalPdf = await Promise.all([
    page.waitForEvent("download"),
    page.locator("#first .journal-pdf").click(),
  ]);
  assert.equal(journalPdf[0].suggestedFilename(), "journal.pdf");
  console.log("browser card assertions: PASS");
} finally {
  await browser.close();
}
