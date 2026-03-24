// @vitest-environment jsdom

import React from "react";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { LocationModal } from "./location-modal";
import { jsonResponse } from "./test-helpers";

describe("LocationModal", () => {
  afterEach(() => {
    cleanup();
    vi.restoreAllMocks();
  });

  it("returns null without a preview and renders successful lookups", async () => {
    const { container } = render(<LocationModal preview={null} onClose={vi.fn()} />);
    expect(container.textContent).toBe("");

    global.fetch = vi.fn(async () => jsonResponse({ item: { lat: 52.23, lon: 21.01 } }));
    Object.defineProperty(navigator, "geolocation", {
      configurable: true,
      value: {
        getCurrentPosition(success) {
          success({ coords: { latitude: 52.23, longitude: 21.01 } });
        },
      },
    });

    render(<LocationModal preview={{ title: "BMW X1", location: "Warsaw" }} onClose={vi.fn()} />);

    expect(await screen.findByTitle("BMW X1 map")).toBeTruthy();
    expect(await screen.findByText("Your location is available for distance calculations.")).toBeTruthy();
  });

  it("shows geocoding errors", async () => {
    global.fetch = vi.fn(async () => ({
      ok: false,
      headers: { get: () => "application/json" },
      json: async () => ({ detail: "Could not load map preview." }),
    }));
    Object.defineProperty(navigator, "geolocation", {
      configurable: true,
      value: undefined,
    });

    render(<LocationModal preview={{ title: "BMW X1", location: "Warsaw" }} onClose={vi.fn()} />);

    await waitFor(() => {
      expect(screen.getByText("Could not load map preview.")).toBeTruthy();
    });
  });
});
