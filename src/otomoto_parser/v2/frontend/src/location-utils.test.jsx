// @vitest-environment jsdom

import { afterEach, describe, expect, it, vi } from "vitest";

import { buildVehicleReportMeta, formatFieldLabel, formatValue, normalizeLookupText } from "./formatters";
import { getGeolocationErrorStatus, getInitialGeolocationPlan } from "./geolocation";
import {
  buildGoogleMapsUrl,
  buildOsmEmbedUrl,
  createPositionRequester,
  formatDistanceChip,
  formatGeolocationStatus,
  getGeolocationButtonLabel,
  haversineKm,
} from "./location-utils";

describe("location and formatting helpers", () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("formats generic values and field labels", () => {
    expect(formatFieldLabel("first_registration-date")).toBe("First registration date");
    expect(formatValue(null)).toBe("—");
    expect(formatValue(true)).toBe("Yes");
    expect(formatValue([])).toBe("—");
    expect(formatValue(["one", "two"])).toBe("one, two");
    expect(normalizeLookupText(" wx 1234 ")).toBe("WX1234");
  });

  it("builds vehicle report metadata for success and failure payloads", () => {
    expect(buildVehicleReportMeta({ report: { ok: true }, retrievedAt: "2026-03-24T12:00:00Z" })).toEqual(
      expect.objectContaining({
        cached: true,
        status: "success",
        retrievedAt: "2026-03-24T12:00:00Z",
        lastError: null,
      }),
    );
    expect(buildVehicleReportMeta({ status: "running", error: "boom" }, "fallback")).toEqual(
      expect.objectContaining({
        status: "running",
        lastError: "fallback",
      }),
    );
  });

  it("builds URLs and distance labels across geolocation states", () => {
    expect(haversineKm({ lat: 52.2297, lon: 21.0122 }, { lat: 52.4064, lon: 16.9252 })).toBeGreaterThan(250);
    expect(buildOsmEmbedUrl(52.23, 21.01)).toContain("openstreetmap.org");
    expect(buildGoogleMapsUrl("Warsaw, Poland")).toContain("Warsaw%2C%20Poland");
    expect(formatDistanceChip(null, { status: "idle" }, null)).toBe("No location");
    expect(formatDistanceChip("Warsaw", { status: "denied" }, null)).toBe("Location blocked");
    expect(formatDistanceChip("Warsaw", { status: "unavailable" }, null)).toBe("Location unavailable");
    expect(formatDistanceChip("Warsaw", { status: "error" }, null)).toBe("Retry location");
    expect(formatDistanceChip("Warsaw", { status: "prompt" }, null)).toBe("Enable location");
    expect(formatDistanceChip("Warsaw", { status: "requesting" }, null)).toBe("Requesting location...");
    expect(formatDistanceChip("Warsaw", { status: "ready", coords: null }, null)).toBe("Locating you...");
    expect(formatDistanceChip("Warsaw", { status: "ready", coords: { lat: 52.23, lon: 21.01 } }, { status: "loading" })).toBe("Finding place...");
    expect(formatDistanceChip("Warsaw", { status: "ready", coords: { lat: 52.23, lon: 21.01 } }, { status: "error" })).toBe("Lookup failed");
    expect(
      formatDistanceChip(
        "Warsaw",
        { status: "ready", coords: { lat: 52.23, lon: 21.01 } },
        { status: "ready", coords: { lat: 52.4064, lon: 16.9252 } },
      ),
    ).toContain("km from you");
  });

  it("maps geolocation plans, statuses, and button labels", () => {
    expect(getInitialGeolocationPlan({ hasGeolocation: false, isSecureContext: true, hasPermissionsApi: true, permissionState: "granted" })).toEqual({ status: "unavailable", shouldRequestPosition: false });
    expect(getInitialGeolocationPlan({ hasGeolocation: true, isSecureContext: true, hasPermissionsApi: false, permissionState: "prompt" })).toEqual({ status: "prompt", shouldRequestPosition: false });
    expect(getInitialGeolocationPlan({ hasGeolocation: true, isSecureContext: true, hasPermissionsApi: true, permissionState: "granted" })).toEqual({ status: "idle", shouldRequestPosition: true });
    expect(getInitialGeolocationPlan({ hasGeolocation: true, isSecureContext: true, hasPermissionsApi: true, permissionState: "denied" })).toEqual({ status: "denied", shouldRequestPosition: false });
    expect(getGeolocationErrorStatus({ errorCode: 1 })).toBe("denied");
    expect(getGeolocationErrorStatus({ errorCode: 2, permissionState: "prompt" })).toBe("error");
    expect(formatGeolocationStatus({ status: "ready" })).toBe("Distance enabled");
    expect(formatGeolocationStatus({ status: "requesting" })).toBe("Requesting location...");
    expect(formatGeolocationStatus({ status: "denied" })).toBe("Location blocked in browser permissions");
    expect(formatGeolocationStatus({ status: "unavailable", unavailableReason: "insecure-context" })).toBe("Location is unavailable in this browser context");
    expect(formatGeolocationStatus({ status: "unavailable", unavailableReason: "unsupported" })).toBe("Location is not supported in this browser");
    expect(formatGeolocationStatus({ status: "error" })).toBe("Location request failed. Try again.");
    expect(formatGeolocationStatus({ status: "idle" })).toBe("Enable location to show distances");
    expect(getGeolocationButtonLabel({ status: "ready" })).toBe("Refresh location");
    expect(getGeolocationButtonLabel({ status: "requesting" })).toBe("Requesting...");
    expect(getGeolocationButtonLabel({ status: "error" })).toBe("Retry location");
    expect(getGeolocationButtonLabel({ status: "unavailable", unavailableReason: "insecure-context" })).toBe("Location requires HTTPS");
    expect(getGeolocationButtonLabel({ status: "unavailable", unavailableReason: "unsupported" })).toBe("Location unsupported");
    expect(getGeolocationButtonLabel({ status: "idle" })).toBe("Enable location");
  });

  it("creates geolocation requesters for unavailable and in-flight cases", () => {
    const update = vi.fn();
    const inFlightRef = { current: false };
    const originalGeolocation = navigator.geolocation;
    const originalSecureContext = window.isSecureContext;

    Object.defineProperty(navigator, "geolocation", { configurable: true, value: undefined });
    createPositionRequester(update, inFlightRef)();
    expect(update).toHaveBeenLastCalledWith({ status: "unavailable", coords: null, unavailableReason: "unsupported" });

    Object.defineProperty(navigator, "geolocation", { configurable: true, value: { getCurrentPosition: vi.fn() } });
    Object.defineProperty(window, "isSecureContext", { configurable: true, value: false });
    createPositionRequester(update, inFlightRef)();
    expect(update).toHaveBeenLastCalledWith({ status: "unavailable", coords: null, unavailableReason: "insecure-context" });

    Object.defineProperty(window, "isSecureContext", { configurable: true, value: true });
    inFlightRef.current = true;
    const getCurrentPosition = vi.fn();
    Object.defineProperty(navigator, "geolocation", { configurable: true, value: { getCurrentPosition } });
    createPositionRequester(update, inFlightRef)();
    expect(getCurrentPosition).not.toHaveBeenCalled();

    Object.defineProperty(navigator, "geolocation", { configurable: true, value: originalGeolocation });
    Object.defineProperty(window, "isSecureContext", { configurable: true, value: originalSecureContext });
  });

  it("updates geolocation state for success and permission fallback errors", async () => {
    const originalGeolocation = navigator.geolocation;
    const originalPermissions = navigator.permissions;
    const originalSecureContext = window.isSecureContext;
    const updates = [];
    const inFlightRef = { current: false };
    const update = vi.fn((value) => {
      if (typeof value === "function") {
        updates.push(value({ status: "idle", coords: null }));
        return;
      }
      updates.push(value);
    });

    Object.defineProperty(window, "isSecureContext", { configurable: true, value: true });
    Object.defineProperty(navigator, "permissions", {
      configurable: true,
      value: {
        query: vi.fn(async () => ({ state: "denied" })),
      },
    });
    Object.defineProperty(navigator, "geolocation", {
      configurable: true,
      value: {
        getCurrentPosition(success) {
          success({ coords: { latitude: 52.23, longitude: 21.01 } });
        },
      },
    });

    createPositionRequester(update, inFlightRef)();
    expect(updates.at(-1)).toEqual({ status: "ready", coords: { lat: 52.23, lon: 21.01 }, unavailableReason: null });

    updates.length = 0;
    inFlightRef.current = false;
    Object.defineProperty(navigator, "geolocation", {
      configurable: true,
      value: {
        getCurrentPosition(success, error) {
          error({ code: 1 });
        },
      },
    });
    createPositionRequester(update, inFlightRef)();
    await vi.waitFor(() => {
      expect(updates.at(-1)).toEqual({ status: "denied", coords: null, unavailableReason: null });
    });

    updates.length = 0;
    Object.defineProperty(navigator, "permissions", { configurable: true, value: undefined });
    createPositionRequester(update, inFlightRef)();
    expect(updates.at(-1)).toEqual({ status: "denied", coords: null, unavailableReason: null });

    Object.defineProperty(navigator, "geolocation", { configurable: true, value: originalGeolocation });
    Object.defineProperty(navigator, "permissions", { configurable: true, value: originalPermissions });
    Object.defineProperty(window, "isSecureContext", { configurable: true, value: originalSecureContext });
  });
});
