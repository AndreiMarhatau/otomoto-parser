// @vitest-environment jsdom

import React from "react";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { useResultsGeolocation } from "./use-results-geolocation";
import { jsonResponse } from "./test-helpers";

function GeolocationHarness({ results = { items: [] }, currentItems = [{ location: "Warsaw" }] }) {
  const state = useResultsGeolocation(results, currentItems);
  return (
    <div>
      <button
        type="button"
        onClick={() => state.updateGeolocationState({ status: "denied", coords: null, unavailableReason: null })}
      >
        mark-denied
      </button>
      <button
        type="button"
        onClick={() => state.updateGeolocationState({ status: "ready", coords: { lat: 52.23, lon: 21.01 }, unavailableReason: null })}
      >
        mark-ready
      </button>
      <p>{state.geolocationState.status}</p>
      <p>{state.locationCache.Warsaw?.status || "no-cache"}</p>
    </div>
  );
}

describe("useResultsGeolocation", () => {
  afterEach(() => {
    cleanup();
    vi.restoreAllMocks();
  });

  it("preserves denied state when the permissions query fails", async () => {
    Object.defineProperty(window, "isSecureContext", { configurable: true, value: true });
    Object.defineProperty(navigator, "geolocation", {
      configurable: true,
      value: { getCurrentPosition: vi.fn() },
    });
    Object.defineProperty(navigator, "permissions", {
      configurable: true,
      value: {
        query: vi.fn(async () => {
          throw new Error("permissions failed");
        }),
      },
    });

    render(<GeolocationHarness />);
    fireEvent.click(screen.getByText("mark-denied"));

    await waitFor(() => {
      expect(screen.getByText("denied")).toBeTruthy();
    });
  });

  it("stores geocode lookup failures in the location cache", async () => {
    Object.defineProperty(window, "isSecureContext", { configurable: true, value: true });
    Object.defineProperty(navigator, "geolocation", {
      configurable: true,
      value: { getCurrentPosition: vi.fn() },
    });
    Object.defineProperty(navigator, "permissions", {
      configurable: true,
      value: {
        query: vi.fn(async () => ({ state: "prompt", onchange: null })),
      },
    });
    global.fetch = vi.fn(async (path) => {
      if (path === "/api/geocode/batch") {
        throw new Error("geocode failed");
      }
      return jsonResponse({ item: {} });
    });

    render(<GeolocationHarness />);
    fireEvent.click(screen.getByText("mark-ready"));

    await waitFor(() => {
      expect(screen.getByText("error")).toBeTruthy();
    });
  });
});
