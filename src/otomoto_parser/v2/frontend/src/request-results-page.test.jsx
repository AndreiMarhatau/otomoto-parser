// @vitest-environment jsdom

import { cleanup, fireEvent, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { buildResultsPayload, installFetchMock, jsonResponse, renderResultsPage } from "./test-helpers";

describe("RequestResultsPage geolocation bootstrap", () => {
  let originalGeolocation;
  let originalPermissions;
  let originalSecureContext;

  beforeEach(() => {
    installFetchMock();
    originalGeolocation = navigator.geolocation;
    originalPermissions = navigator.permissions;
    originalSecureContext = window.isSecureContext;
    window.scrollTo = vi.fn();
    window.requestAnimationFrame = vi.fn((callback) => {
      callback();
      return 1;
    });
    window.cancelAnimationFrame = vi.fn();
    Object.defineProperty(window, "isSecureContext", {
      configurable: true,
      value: true,
    });
  });

  afterEach(() => {
    cleanup();
    vi.restoreAllMocks();
    Object.defineProperty(window, "isSecureContext", {
      configurable: true,
      value: originalSecureContext,
    });
    Object.defineProperty(navigator, "geolocation", {
      configurable: true,
      value: originalGeolocation,
    });
    Object.defineProperty(navigator, "permissions", {
      configurable: true,
      value: originalPermissions,
    });
  });

  it("auto-requests location when permissions.query resolves to granted", async () => {
    const getCurrentPosition = vi.fn((success) => {
      success({ coords: { latitude: 52.23, longitude: 21.01 } });
    });
    Object.defineProperty(navigator, "geolocation", {
      configurable: true,
      value: { getCurrentPosition },
    });
    Object.defineProperty(navigator, "permissions", {
      configurable: true,
      value: {
        query: vi.fn(async () => ({ state: "granted", onchange: null })),
      },
    });

    renderResultsPage();

    await screen.findByText("1 listings");
    await waitFor(() => {
      expect(navigator.permissions.query).toHaveBeenCalledWith({ name: "geolocation" });
      expect(getCurrentPosition).toHaveBeenCalledTimes(1);
    });
    expect(await screen.findByText("Refresh location")).toBeTruthy();
  });

  it("shows blocked and does not request location when permissions.query resolves to denied", async () => {
    const getCurrentPosition = vi.fn();
    Object.defineProperty(navigator, "geolocation", {
      configurable: true,
      value: { getCurrentPosition },
    });
    Object.defineProperty(navigator, "permissions", {
      configurable: true,
      value: {
        query: vi.fn(async () => ({ state: "denied", onchange: null })),
      },
    });

    renderResultsPage();

    await screen.findByText("1 listings");
    await waitFor(() => {
      expect(navigator.permissions.query).toHaveBeenCalledWith({ name: "geolocation" });
      expect(getCurrentPosition).not.toHaveBeenCalled();
    });
    expect(await screen.findByText("Location blocked in browser permissions")).toBeTruthy();
    expect(await screen.findByText("Location blocked")).toBeTruthy();
  });

  it("keeps promptable permission in enable state and does not auto-request", async () => {
    const getCurrentPosition = vi.fn();
    Object.defineProperty(navigator, "geolocation", {
      configurable: true,
      value: { getCurrentPosition },
    });
    Object.defineProperty(navigator, "permissions", {
      configurable: true,
      value: {
        query: vi.fn(async () => ({ state: "prompt", onchange: null })),
      },
    });

    renderResultsPage();

    await screen.findByText("1 listings");
    await waitFor(() => {
      expect(navigator.permissions.query).toHaveBeenCalledWith({ name: "geolocation" });
      expect(getCurrentPosition).not.toHaveBeenCalled();
    });
    expect(await screen.findAllByText("Enable location")).toHaveLength(2);
  });

  it("requests location when the user clicks Enable location", async () => {
    const getCurrentPosition = vi.fn((success) => {
      success({ coords: { latitude: 52.23, longitude: 21.01 } });
    });
    Object.defineProperty(navigator, "geolocation", {
      configurable: true,
      value: { getCurrentPosition },
    });
    Object.defineProperty(navigator, "permissions", {
      configurable: true,
      value: {
        query: vi.fn(async () => ({ state: "prompt", onchange: null })),
      },
    });

    renderResultsPage();

    const enableButton = await screen.findByRole("button", { name: "Enable location" });
    expect(getCurrentPosition).not.toHaveBeenCalled();

    fireEvent.click(enableButton);

    await waitFor(() => {
      expect(getCurrentPosition).toHaveBeenCalledTimes(1);
    });
    expect(await screen.findByText("Refresh location")).toBeTruthy();
  });

  it("falls back to prompt state when the Permissions API is unavailable", async () => {
    const getCurrentPosition = vi.fn();
    Object.defineProperty(navigator, "geolocation", {
      configurable: true,
      value: { getCurrentPosition },
    });
    Object.defineProperty(navigator, "permissions", {
      configurable: true,
      value: undefined,
    });

    renderResultsPage();

    await screen.findByText("1 listings");
    await waitFor(() => {
      expect(getCurrentPosition).not.toHaveBeenCalled();
    });
    expect(await screen.findAllByText("Enable location")).toHaveLength(2);
  });

  it("renders geolocation as unavailable in an insecure browser context", async () => {
    const getCurrentPosition = vi.fn();
    Object.defineProperty(window, "isSecureContext", {
      configurable: true,
      value: false,
    });
    Object.defineProperty(navigator, "geolocation", {
      configurable: true,
      value: { getCurrentPosition },
    });
    Object.defineProperty(navigator, "permissions", {
      configurable: true,
      value: {
        query: vi.fn(async () => ({ state: "prompt", onchange: null })),
      },
    });

    renderResultsPage();

    const locationButton = await screen.findByRole("button", { name: "Location requires HTTPS" });
    expect(locationButton).toHaveProperty("disabled", true);
    expect(await screen.findByText("Location is unavailable in this browser context")).toBeTruthy();
    expect(await screen.findByText("Location unavailable")).toBeTruthy();
    fireEvent.click(locationButton);
    expect(getCurrentPosition).not.toHaveBeenCalled();
    expect(navigator.permissions.query).not.toHaveBeenCalled();
  });

  it("renders geolocation as unsupported when navigator.geolocation is unavailable", async () => {
    Object.defineProperty(navigator, "geolocation", {
      configurable: true,
      value: undefined,
    });
    Object.defineProperty(navigator, "permissions", {
      configurable: true,
      value: {
        query: vi.fn(async () => ({ state: "prompt", onchange: null })),
      },
    });

    renderResultsPage();

    const locationButton = await screen.findByRole("button", { name: "Location unsupported" });
    expect(locationButton).toHaveProperty("disabled", true);
    expect(await screen.findByText("Location is not supported in this browser")).toBeTruthy();
    expect(await screen.findByText("Location unavailable")).toBeTruthy();
    fireEvent.click(locationButton);
    expect(navigator.permissions.query).not.toHaveBeenCalled();
  });

  it("preserves ready state across results refreshes when the Permissions API is unavailable", async () => {
    const getCurrentPosition = vi.fn((success) => {
      success({ coords: { latitude: 52.23, longitude: 21.01 } });
    });
    Object.defineProperty(navigator, "geolocation", {
      configurable: true,
      value: { getCurrentPosition },
    });
    Object.defineProperty(navigator, "permissions", {
      configurable: true,
      value: undefined,
    });

    renderResultsPage();

    const enableButton = await screen.findByRole("button", { name: "Enable location" });
    fireEvent.click(enableButton);

    await waitFor(() => {
      expect(getCurrentPosition).toHaveBeenCalledTimes(1);
    });
    expect(await screen.findByText("Refresh location")).toBeTruthy();

    fireEvent.change(screen.getByDisplayValue("12"), { target: { value: "24" } });

    await waitFor(() => {
      expect(global.fetch).toHaveBeenCalledWith(
        expect.stringContaining("page_size=24"),
        expect.any(Object),
      );
    });
    expect(await screen.findByText("Refresh location")).toBeTruthy();
    expect(await screen.findByText("Distance enabled")).toBeTruthy();
  });

  it("preserves denied classification when manual geolocation fails and follow-up permissions query rejects", async () => {
    const getCurrentPosition = vi.fn((success, error) => {
      error({ code: 1 });
    });
    let queryCalls = 0;
    const permissionStatus = { state: "prompt", onchange: null };
    const query = vi.fn(async () => {
      queryCalls += 1;
      if (queryCalls === 2) {
        throw new Error("permissions query failed after prompt");
      }
      return permissionStatus;
    });
    Object.defineProperty(navigator, "geolocation", {
      configurable: true,
      value: { getCurrentPosition },
    });
    Object.defineProperty(navigator, "permissions", {
      configurable: true,
      value: { query },
    });

    renderResultsPage();

    const enableButton = await screen.findByRole("button", { name: "Enable location" });
    fireEvent.click(enableButton);

    await waitFor(() => {
      expect(getCurrentPosition).toHaveBeenCalledTimes(1);
      expect(query.mock.calls.length).toBeGreaterThanOrEqual(2);
    });
    expect(await screen.findByText("Location blocked in browser permissions")).toBeTruthy();
    expect(await screen.findByText("Location blocked")).toBeTruthy();
  });

  it("keeps transient geolocation failures retryable in supported browsers", async () => {
    const getCurrentPosition = vi.fn((success, error) => {
      error({ code: 3 });
    });
    const query = vi.fn(async () => ({ state: "prompt", onchange: null }));
    Object.defineProperty(navigator, "geolocation", {
      configurable: true,
      value: { getCurrentPosition },
    });
    Object.defineProperty(navigator, "permissions", {
      configurable: true,
      value: { query },
    });

    renderResultsPage();

    const locationButton = await screen.findByRole("button", { name: "Enable location" });
    fireEvent.click(locationButton);

    await waitFor(() => {
      expect(getCurrentPosition).toHaveBeenCalledTimes(1);
    });

    const retryButton = await screen.findByRole("button", { name: "Retry location" });
    expect(retryButton).toHaveProperty("disabled", false);
    expect(await screen.findByText("Location request failed. Try again.")).toBeTruthy();
    expect((await screen.findAllByText("Retry location")).length).toBeGreaterThanOrEqual(1);

    fireEvent.click(retryButton);

    await waitFor(() => {
      expect(getCurrentPosition).toHaveBeenCalledTimes(2);
    });
    expect(query.mock.calls.length).toBeGreaterThanOrEqual(2);
  });

  it("updates the UI when PermissionStatus.onchange fires after initial render", async () => {
    const getCurrentPosition = vi.fn();
    const permissionStatus = {
      state: "prompt",
      onchange: null,
    };
    Object.defineProperty(navigator, "geolocation", {
      configurable: true,
      value: { getCurrentPosition },
    });
    Object.defineProperty(navigator, "permissions", {
      configurable: true,
      value: {
        query: vi.fn(async () => permissionStatus),
      },
    });

    renderResultsPage();

    await screen.findByText("1 listings");
    expect(await screen.findAllByText("Enable location")).toHaveLength(2);
    expect(typeof permissionStatus.onchange).toBe("function");

    permissionStatus.state = "denied";
    permissionStatus.onchange();

    expect(await screen.findByText("Location blocked in browser permissions")).toBeTruthy();
    expect(await screen.findByText("Location blocked")).toBeTruthy();
    expect(getCurrentPosition).not.toHaveBeenCalled();
  });

  it("opens listing location previews, category picker, and vehicle reports", async () => {
    window.prompt = vi.fn((_, initialValue) => (initialValue ? `${initialValue} renamed` : "Fresh category"));
    window.confirm = vi.fn(() => true);
    installFetchMock();
    const defaultFetch = global.fetch;
    const resultsPayload = buildResultsPayload();
    resultsPayload.categories = {
      Favorites: { label: "Favorites", count: 1, kind: "system", editable: true, deletable: true },
    };
    resultsPayload.currentCategory = "Favorites";
    resultsPayload.assignableCategories = [{ key: "Favorites", label: "Favorites" }];
    resultsPayload.items[0].category = "Favorites";
    resultsPayload.items[0].savedCategoryKeys = ["Favorites"];
    global.fetch = vi.fn(async (path, options = {}) => {
      if (String(path).startsWith("/api/requests/req-1/results")) {
        return jsonResponse(resultsPayload);
      }
      if (path === "/api/settings") {
        return jsonResponse({ item: { openaiApiKeyConfigured: true } });
      }
      if (path === "/api/geocode/batch") {
        return jsonResponse({ items: {} });
      }
      if (String(path).startsWith("/api/geocode?query=")) {
        return jsonResponse({ item: { lat: 52.23, lon: 21.01 } });
      }
      if (path === "/api/requests/req-1/listings/listing-1/categories" && options.method === "PUT") {
        return jsonResponse({ ok: true });
      }
      if (path === "/api/requests/req-1/categories" && options.method === "POST") {
        return jsonResponse({ item: { key: "fresh-category", label: "Fresh category", kind: "custom", editable: true, deletable: true } });
      }
      if (path === "/api/requests/req-1/categories/Favorites" && options.method === "PATCH") {
        return jsonResponse({ item: { key: "Favorites", label: "Favorites renamed" } });
      }
      if (path === "/api/requests/req-1/categories/Favorites" && options.method === "DELETE") {
        return jsonResponse({ ok: true });
      }
      if (path === "/api/requests/req-1/listings/listing-1/vehicle-report") {
        return jsonResponse({
          item: {
            report: {
              api_version: "1.0.20",
              technical_data: { make: "BMW" },
              autodna_data: {},
              carfax_data: {},
              timeline_data: [],
            },
            retrievedAt: "2026-03-24T12:00:00Z",
            identity: { advertId: "adv-1", vin: "VIN123", registrationNumber: "WW2222C" },
            summary: { make: "BMW", model: "X1" },
          },
        });
      }
      if (path === "/api/requests/req-1/listings/listing-1/red-flags") {
        return jsonResponse({ item: { status: "idle" } });
      }
      return defaultFetch(path, options);
    });
    Object.defineProperty(navigator, "geolocation", {
      configurable: true,
      value: undefined,
    });
    Object.defineProperty(navigator, "permissions", {
      configurable: true,
      value: undefined,
    });

    renderResultsPage();

    await screen.findByText("1 listings");

    fireEvent.click(screen.getByRole("button", { name: "Warsaw" }));
    expect(await screen.findByText("Loading map preview...")).toBeTruthy();
    expect(await screen.findByTitle("Test listing map")).toBeTruthy();

    fireEvent.click(screen.getByRole("button", { name: "Save 1" }));
    fireEvent.click(screen.getByRole("checkbox"));
    fireEvent.mouseDown(document.body);
    await waitFor(() => {
      expect(global.fetch).toHaveBeenCalledWith(
        "/api/requests/req-1/listings/listing-1/categories",
        expect.objectContaining({ method: "PUT" }),
      );
    });

    fireEvent.click(screen.getByRole("button", { name: "Add category" }));
    fireEvent.click(screen.getByRole("button", { name: "Rename category" }));
    fireEvent.click(screen.getByRole("button", { name: "Delete category" }));

    fireEvent.click(screen.getByRole("button", { name: "Vehicle report" }));
    expect(await screen.findByText("View report")).toBeTruthy();
    expect(screen.getAllByText("BMW").length).toBeGreaterThan(0);
    expect(global.fetch).toHaveBeenCalledWith("/api/requests/req-1/categories", expect.objectContaining({ method: "POST" }));
    expect(global.fetch).toHaveBeenCalledWith("/api/requests/req-1/categories/Favorites", expect.objectContaining({ method: "PATCH" }));
    expect(global.fetch).toHaveBeenCalledWith("/api/requests/req-1/categories/Favorites", expect.objectContaining({ method: "DELETE" }));
  });
});
