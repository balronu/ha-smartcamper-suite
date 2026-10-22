export type CardConfig = { type: string; module: string; vehicle_id?: string };

const MODULES = new Set(["travel_journal", "fuel_stations", "route_planner", "border_forecast"]);

export function validateConfig(config: CardConfig): CardConfig {
  if (!MODULES.has(config.module)) throw new Error("Unknown SmartCamper module");
  return config;
}
