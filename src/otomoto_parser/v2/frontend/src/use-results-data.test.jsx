// @vitest-environment jsdom

import React from "react";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { useResultsData } from "./use-results-data";
import { jsonResponse } from "./test-helpers";

function ResultsDataHarness({ requestId = "req-1" }) {
  const state = useResultsData(requestId);
  return (
    <div>
      <button type="button" onClick={() => void state.createCategory()}>create-category</button>
      <button
        type="button"
        onClick={() =>
          state.updateVehicleReportResultItem("listing-1", {
            report: { ok: true },
            retrievedAt: "2026-03-24T12:00:00Z",
          })
        }
      >
        update-report
      </button>
      <button type="button" onClick={() => state.setActiveCategory("Favorites")}>set-category</button>
      <button type="button" onClick={() => state.bumpResultsReload()}>reload-results</button>
      <p>{state.requestLoading ? "loading" : "loaded"}</p>
      <p>{state.request?.id || "no-request"}</p>
      <p>{state.activeCategory}</p>
      <p>{state.resultsError || "no-error"}</p>
      <p>{state.results?.currentCategory || "no-results"}</p>
      <p>{state.results?.items?.[0]?.vehicleReport?.status || "no-report"}</p>
      <p>{state.settingsData?.item ? "settings-loaded" : "no-settings"}</p>
    </div>
  );
}

describe("useResultsData", () => {
  beforeEach(() => {
    window.prompt = vi.fn(() => "Fresh category");
  });

  afterEach(() => {
    cleanup();
    vi.restoreAllMocks();
  });

  it("loads results, syncs categories, creates categories, and updates report metadata", async () => {
    global.fetch = vi.fn(async (path, options = {}) => {
      if (path === "/api/requests/req-1") {
        return jsonResponse({ item: { id: "req-1", resultsReady: true } });
      }
      if (path === "/api/settings") {
        return jsonResponse({ item: { openaiApiKeyConfigured: true } });
      }
      if (String(path).startsWith("/api/requests/req-1/results?")) {
        return jsonResponse({
          currentCategory: "Favorites",
          categories: { Favorites: { label: "Favorites", count: 1, kind: "system" } },
          assignableCategories: [],
          items: [{ id: "listing-1" }],
          pagination: { page: 1, totalPages: 1, totalItems: 1 },
        });
      }
      if (path === "/api/requests/req-1/categories" && options.method === "POST") {
        return jsonResponse({
          item: { key: "fresh-category", label: "Fresh category", kind: "custom", editable: true, deletable: true },
        });
      }
      throw new Error(`Unhandled fetch path: ${path}`);
    });

    render(<ResultsDataHarness />);

    await screen.findByText("req-1");
    await screen.findByText("settings-loaded");
    await waitFor(() => {
      expect(screen.getAllByText("Favorites").length).toBeGreaterThan(0);
    });

    fireEvent.click(screen.getByText("create-category"));
    await waitFor(() => {
      expect(global.fetch).toHaveBeenCalledWith(
        "/api/requests/req-1/categories",
        expect.objectContaining({ method: "POST" }),
      );
    });

    fireEvent.click(screen.getByText("update-report"));
    expect(await screen.findByText("success")).toBeTruthy();
  });

  it("handles cancelled creation, result failures, and request-id resets", async () => {
    let resultsCalls = 0;
    let failCategoryCreation = false;
    window.prompt = vi.fn(() => null);
    global.fetch = vi.fn(async (path, options = {}) => {
      if (path === "/api/requests/req-1") {
        return jsonResponse({ item: { id: "req-1", resultsReady: false } });
      }
      if (path === "/api/requests/req-2") {
        return jsonResponse({ item: { id: "req-2", resultsReady: true } });
      }
      if (path === "/api/settings") {
        return jsonResponse({ item: {} });
      }
      if (String(path).startsWith("/api/requests/req-1/results?")) {
        resultsCalls += 1;
        if (resultsCalls === 1) {
          throw new Error("results failed");
        }
        return jsonResponse({
          currentCategory: "Price evaluation out of range",
          categories: {},
          assignableCategories: [],
          items: [],
          pagination: { page: 1, totalPages: 1, totalItems: 0 },
        });
      }
      if (String(path).startsWith("/api/requests/req-2/results?")) {
        return jsonResponse({
          currentCategory: "Favorites",
          categories: {},
          assignableCategories: [],
          items: [],
          pagination: { page: 1, totalPages: 1, totalItems: 0 },
        });
      }
      if (path === "/api/requests/req-2/categories" && options.method === "POST") {
        if (failCategoryCreation) {
          throw new Error("category create failed");
        }
        return jsonResponse({
          item: { key: "fresh-category", label: "Fresh category", kind: "custom", editable: true, deletable: true },
        });
      }
      throw new Error(`Unhandled fetch path: ${path}`);
    });

    const { rerender } = render(<ResultsDataHarness requestId="req-1" />);

    await screen.findByText("results failed");
    fireEvent.click(screen.getByText("create-category"));
    expect(global.fetch).not.toHaveBeenCalledWith(
      "/api/requests/req-1/categories",
      expect.anything(),
    );

    await new Promise((resolve) => window.setTimeout(resolve, 3100));
    await waitFor(() => {
      expect(screen.getAllByText("Price evaluation out of range").length).toBeGreaterThan(0);
    });

    rerender(<ResultsDataHarness requestId="req-2" />);
    await screen.findByText("req-2");
    await waitFor(() => {
      expect(screen.getAllByText("Favorites").length).toBeGreaterThan(0);
    });

    failCategoryCreation = true;
    window.prompt = vi.fn(() => "Fresh category");
    fireEvent.click(screen.getByText("create-category"));
    await screen.findByText("category create failed");
  });
});
