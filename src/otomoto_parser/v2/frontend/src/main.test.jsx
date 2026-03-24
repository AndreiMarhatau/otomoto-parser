// @vitest-environment jsdom

import React from "react";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes, useNavigate } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { RequestDetailPage, RequestResultsPage, SettingsPage, usePolling } from "./main";

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

function renderSettingsPage() {
  return render(
    <React.StrictMode>
      <MemoryRouter initialEntries={["/settings"]}>
        <Routes>
          <Route path="/settings" element={<SettingsPage />} />
        </Routes>
      </MemoryRouter>
    </React.StrictMode>,
  );
}

function PollingHarness({ target, enabled = false }) {
  const { data, loading, error } = usePolling(() => Promise.resolve({ item: { label: target } }), enabled, target);

  if (loading && !data) {
    return <p>Loading {target}</p>;
  }
  if (error) {
    return <p>{error.message}</p>;
  }
  return <p>{data?.item?.label}</p>;
}

function RequestDetailPageTestShell() {
  const navigate = useNavigate();
  return (
    <>
      <button type="button" onClick={() => navigate("/requests/req-2")}>
        Open request 2
      </button>
      <Routes>
        <Route path="/requests/:requestId" element={<RequestDetailPage />} />
      </Routes>
    </>
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

describe("SettingsPage polling regression", () => {
  afterEach(() => {
    cleanup();
    vi.restoreAllMocks();
  });

  it("does not re-fetch /api/settings in a tight loop when polling is disabled", async () => {
    const fetchMock = vi.fn(async (path) => {
      if (path === "/api/settings") {
        return jsonResponse({
          item: {
            openaiApiKeyConfigured: false,
            openaiApiKeySource: null,
            openaiApiKeyMasked: null,
            openaiApiKeyStored: false,
          },
        });
      }
      throw new Error(`Unhandled fetch path: ${path}`);
    });
    global.fetch = fetchMock;

    renderSettingsPage();

    expect(await screen.findByText("Configured")).toBeTruthy();

    const initialSettingsCalls = fetchMock.mock.calls.filter(([path]) => path === "/api/settings").length;
    expect(initialSettingsCalls).toBeLessThanOrEqual(2);

    await new Promise((resolve) => {
      window.setTimeout(resolve, 100);
    });

    const finalSettingsCalls = fetchMock.mock.calls.filter(([path]) => path === "/api/settings").length;
    expect(finalSettingsCalls).toBe(initialSettingsCalls);
  });

  it("re-fetches immediately when the reload key changes while polling is disabled", async () => {
    const { rerender } = render(<PollingHarness target="alpha" enabled={false} />);

    expect(await screen.findByText("alpha")).toBeTruthy();

    rerender(<PollingHarness target="beta" enabled={false} />);

    expect(await screen.findByText("beta")).toBeTruthy();
  });
});

describe("RequestDetailPage polling", () => {
  afterEach(() => {
    cleanup();
    vi.restoreAllMocks();
  });

  it("re-fetches request data immediately when the route param changes", async () => {
    const fetchMock = vi.fn(async (path) => {
      if (path === "/api/requests/req-1") {
        return jsonResponse({
          item: {
            id: "req-1",
            sourceUrl: "https://example.invalid/req-1",
            status: "ready",
            pagesCompleted: 1,
            resultsWritten: 10,
            resultsReady: true,
            excelReady: false,
            progressMessage: "Request one ready",
            error: null,
          },
        });
      }
      if (path === "/api/requests/req-2") {
        return jsonResponse({
          item: {
            id: "req-2",
            sourceUrl: "https://example.invalid/req-2",
            status: "ready",
            pagesCompleted: 2,
            resultsWritten: 20,
            resultsReady: true,
            excelReady: true,
            progressMessage: "Request two ready",
            error: null,
          },
        });
      }
      throw new Error(`Unhandled fetch path: ${path}`);
    });
    global.fetch = fetchMock;

    render(
      <MemoryRouter initialEntries={["/requests/req-1"]}>
        <RequestDetailPageTestShell />
      </MemoryRouter>,
    );

    expect(await screen.findByText("Request req-1")).toBeTruthy();
    expect(await screen.findByText("Request one ready")).toBeTruthy();

    fireEvent.click(screen.getByRole("button", { name: "Open request 2" }));

    expect(await screen.findByText("Request req-2")).toBeTruthy();
    expect(await screen.findByText("Request two ready")).toBeTruthy();

    expect(fetchMock).toHaveBeenCalledWith("/api/requests/req-2", expect.any(Object));
  });
});
