import { describe, expect, it } from "vitest";
import { renderFuelStationsHtml, renderFuelStateHtml, selectVehicle, validateConfig } from "../src/config";

describe("SmartCamper card config", () => {
  it("accepts one known module and optional vehicle", () => {
    expect(validateConfig({ type: "custom:smartcamper-card", module: "route_planner", vehicle_id: "vehicle-1" }).module).toBe("route_planner");
  });
  it("rejects unknown modules", () => {
    expect(() => validateConfig({ type: "custom:smartcamper-card", module: "unknown" })).toThrow();
  });
  it("selects an available vehicle without replacing an explicit choice", () => {
    const states = { "sensor.womo": { attributes: { vehicle_id: "womo" } } };
    expect(selectVehicle({ type: "custom:smartcamper-card", module: "fuel_stations" }, states)).toBe("womo");
    expect(selectVehicle({ type: "custom:smartcamper-card", module: "fuel_stations", vehicle_id: "opel" }, states)).toBe("opel");
  });
  it("renders station fields and escapes untrusted station names", () => {
    const html = renderFuelStationsHtml([
      { station_id: "1", name: "<script>x</script>", price: 1.799, distance_km: 2.1, address: "Main 1", is_open: true },
    ], { type: "custom:smartcamper-card", module: "fuel_stations" });
    expect(html).toContain("&lt;script&gt;x&lt;/script&gt;");
    expect(html).toContain("1.799 €");
    expect(html).toContain("2.1 km");
  });
  it("keeps loading and error states visible", () => {
    const config = { type: "custom:smartcamper-card", module: "fuel_stations" as const };
    expect(renderFuelStateHtml("loading", [], config)).toContain("Lade");
    expect(renderFuelStateHtml("error", [], config)).toContain("nicht geladen");
  });
  it("sorts, limits, and renders multiple fuel prices without inventing values", () => {
    const html = renderFuelStationsHtml([
      { station_id: "far", name: "Far", price: 1.7, distance_km: 9, address: "", is_open: null },
      { station_id: "near", name: "Near", price: 1.8, distance_km: 2, address: "", is_open: null,
        fuel_prices: { diesel: 1.8, e5: null } },
    ], { type: "custom:smartcamper-card", module: "fuel_stations", sort_mode: "distance", visible_station_count: 1 });
    expect(html).toContain("Near");
    expect(html).not.toContain("Far");
    expect(html).toContain("DIESEL: 1.800 €");
    expect(html).toContain("E5: –");
  });
});
