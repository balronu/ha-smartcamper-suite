import { describe, expect, it } from "vitest";
import { validateConfig } from "../src/config";

describe("SmartCamper card config", () => {
  it("accepts one known module and optional vehicle", () => {
    expect(validateConfig({ type: "custom:smartcamper-card", module: "route_planner", vehicle_id: "vehicle-1" }).module).toBe("route_planner");
  });
  it("rejects unknown modules", () => {
    expect(() => validateConfig({ type: "custom:smartcamper-card", module: "unknown" })).toThrow();
  });
});
