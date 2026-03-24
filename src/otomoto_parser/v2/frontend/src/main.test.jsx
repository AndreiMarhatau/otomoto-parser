// @vitest-environment jsdom

import React from "react";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { RequestResultsPage } from "./main";

function jsonResponse(payload) {
  return {
    ok: true,
    status: 200,
    headers: {
      get(name) {
        return name.toLowerCase() === "content-type" ? "application/json" : null;
      },
    },
    json: async () => payload,
  };
}

function buildResultsPayload() {
  return {
    categories: {
      "Price evaluation out of range": {
        label: "Price evaluation out of range",
        count: 1,
        kind: "system",
        editable: false,
        deletable: false,
      },
    },
    currentCategory: "Price evaluation out of range",
    assignableCategories: [],
    items: [
      {
        id: "listing-1",
        title: "Test listing",
        price: 10000,
        priceCurrency: "PLN",
        shortDescription: "Example",
        url: "https://example.invalid/listing-1",
        location: "Warsaw",
        createdAt: "2026-03-24T12:00:00Z",
        category: "Price evaluation out of range",
      },
    ],
    pagination: {
      page: 1,
      totalPages: 1,
      totalItems: 1,
    },
    totalCount: 1,
    generatedAt: "2026-03-24T12:00:00Z",
  };
}

function installFetchMock() {
  global.fetch = vi.fn(async (path) => {
    if (String(path).startsWith("/api/requests/req-1/results")) {
      return jsonResponse(buildResultsPayload());
    }
    if (path === "/api/requests/req-1") {
      return jsonResponse({ item: { id: "req-1", resultsReady: true } });
    }
    if (path === "/api/settings") {
      return jsonResponse({ item: {} });
    }
    if (path === "/api/geocode/batch") {
      return jsonResponse({ items: { Warsaw: { lat: 52.2297, lon: 21.0122 } } });
    }
    throw new Error(`Unhandled fetch path: ${path}`);
  });
}

function renderResultsPage() {
  return render(
    <MemoryRouter initialEntries={["/requests/req-1/results"]}>
      <Routes>
        <Route path="/requests/:requestId/results" element={<RequestResultsPage />} />
      </Routes>
    </MemoryRouter>,
  );
}

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
    expect(await screen.findAllByText("Retry location")).toHaveLength(2);

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
});
