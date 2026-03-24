// @vitest-environment jsdom

import React from "react";
import { render } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { vi } from "vitest";

import { RequestResultsPage } from "./request-results-page";
import { SettingsPage } from "./settings-page";

export function jsonResponse(payload) {
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

export function buildResultsPayload() {
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

export function installFetchMock() {
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

export function renderResultsPage() {
  return render(
    <MemoryRouter initialEntries={["/requests/req-1/results"]}>
      <Routes>
        <Route path="/requests/:requestId/results" element={<RequestResultsPage />} />
      </Routes>
    </MemoryRouter>,
  );
}

export function renderSettingsPage() {
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
