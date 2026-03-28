// @vitest-environment jsdom

import React from "react";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const mockUseResultsData = vi.fn();
const mockUseResultsGeolocation = vi.fn();
const mockUseCategoryActions = vi.fn();
const mockUseReportState = vi.fn();
const mockUseRedFlagState = vi.fn();

vi.mock("./use-results-data", () => ({ useResultsData: (...args) => mockUseResultsData(...args) }));
vi.mock("./use-results-geolocation", () => ({ useResultsGeolocation: (...args) => mockUseResultsGeolocation(...args) }));
vi.mock("./use-category-actions", () => ({ useCategoryActions: (...args) => mockUseCategoryActions(...args) }));
vi.mock("./use-report-state", () => ({ useReportState: (...args) => mockUseReportState(...args) }));
vi.mock("./use-red-flag-state", () => ({ useRedFlagState: (...args) => mockUseRedFlagState(...args) }));
vi.mock("./location-modal", () => ({
  LocationModal: ({ preview, onClose }) => (
    <div>
      <div>{preview ? `${preview.title}:${preview.location}` : "no-preview"}</div>
      <button type="button" onClick={onClose}>close-location</button>
    </div>
  ),
}));
vi.mock("./vehicle-report-modal", () => ({
  VehicleReportModal: ({ state, onClose, onRegenerate, onStartRedFlags, onCancelRedFlags }) => (
    <div>
      <div>{state ? `report:${state.item.id}` : "no-report"}</div>
      <button type="button" onClick={onClose}>close-report</button>
      <button type="button" onClick={() => onRegenerate?.(state?.item)}>regenerate-report</button>
      <button type="button" onClick={() => onStartRedFlags?.(state?.item)}>start-red-flags</button>
      <button type="button" onClick={() => onCancelRedFlags?.(state?.item)}>cancel-red-flags</button>
    </div>
  ),
}));
vi.mock("./listing-card", () => ({
  ListingCard: ({ item, onOpenLocation, onOpenReport }) => (
    <div>
      <button type="button" onClick={() => onOpenLocation({ title: item.title, location: item.location })}>open-location-{item.id}</button>
      <button type="button" onClick={() => onOpenReport(item)}>open-report-{item.id}</button>
      <span>{item.title}</span>
    </div>
  ),
}));

import { RequestResultsPage } from "./request-results-page";

function pageElement() {
  return (
    <MemoryRouter initialEntries={["/requests/req-1/results"]}>
      <Routes>
        <Route path="/requests/:requestId/results" element={<RequestResultsPage />} />
      </Routes>
    </MemoryRouter>
  );
}

function renderPage() {
  return render(pageElement());
}

function baseDataState(overrides = {}) {
  return {
    requestLoading: false,
    request: { id: "req-1", resultsReady: true, progressMessage: "Ready" },
    settingsData: { item: { openaiApiKeyConfigured: true } },
    results: {
      totalCount: 2,
      generatedAt: "2026-03-24T12:00:00Z",
      currentCategory: "Favorites",
      categories: {
        Favorites: { label: "Favorites", count: 2, editable: true, deletable: true },
        Review: { label: "Review", count: 1, editable: false, deletable: false },
      },
      assignableCategories: [],
      items: [{ id: "listing-1", title: "BMW X1", location: "Warsaw" }],
      pagination: { page: 1, totalPages: 6, totalItems: 6 },
    },
    resultsError: null,
    activeCategory: "Favorites",
    setActiveCategory: vi.fn(),
    pageSize: 12,
    setPageSize: vi.fn(),
    currentPage: 1,
    setCurrentPage: vi.fn(),
    categoryBusyByListing: {},
    createCategory: vi.fn(async () => ({ key: "fresh-category" })),
    bumpResultsReload: vi.fn(),
    setResultsError: vi.fn(),
    setCategoryBusyByListing: vi.fn(),
    updateVehicleReportResultItem: vi.fn(),
    ...overrides,
  };
}

describe("RequestResultsPage unit branches", () => {
  beforeEach(() => {
    window.scrollTo = vi.fn();
    window.requestAnimationFrame = vi.fn((callback) => {
      callback();
      return 1;
    });
    window.cancelAnimationFrame = vi.fn();
  });

  afterEach(() => {
    cleanup();
    vi.restoreAllMocks();
  });

  it("renders request-loading and not-ready states", () => {
    mockUseResultsData.mockReturnValue(baseDataState({
      requestLoading: true,
      request: { id: "req-1", resultsReady: false, progressMessage: "Still categorizing" },
      results: null,
    }));
    mockUseResultsGeolocation.mockReturnValue({ geolocationState: { status: "idle" }, locationCache: {}, requestCurrentPosition: vi.fn() });
    mockUseCategoryActions.mockReturnValue({});
    mockUseReportState.mockReturnValue({ vehicleReportState: null, vehicleReportRequestRef: { current: 0 }, setVehicleReportState: vi.fn(), openVehicleReport: vi.fn(), regenerateVehicleReport: vi.fn(), submitVehicleReportLookup: vi.fn(), cancelVehicleReportLookup: vi.fn() });
    mockUseRedFlagState.mockReturnValue({ redFlagState: null, setRedFlagState: vi.fn(), redFlagRequestRef: { current: 0 }, loadRedFlagState: vi.fn(), startRedFlagAnalysis: vi.fn(), cancelRedFlagAnalysis: vi.fn() });

    renderPage();

    expect(screen.getByText("Loading request...")).toBeTruthy();
    expect(screen.getByText("Still categorizing")).toBeTruthy();
  });

  it("renders empty categories, pagination, and local modal state changes", () => {
    const dataState = baseDataState({
      results: {
        totalCount: 0,
        generatedAt: "2026-03-24T12:00:00Z",
        currentCategory: "Favorites",
        categories: { Favorites: { label: "Favorites", count: 0, editable: true, deletable: true } },
        assignableCategories: [],
        items: [],
        pagination: { page: 2, totalPages: 1, totalItems: 0 },
      },
      currentPage: 2,
    });
    mockUseResultsData.mockReturnValue(dataState);
    mockUseResultsGeolocation.mockReturnValue({ geolocationState: { status: "prompt" }, locationCache: {}, requestCurrentPosition: vi.fn() });
    mockUseCategoryActions.mockReturnValue({ createCategoryTab: vi.fn(), renameActiveCategory: vi.fn(), deleteActiveCategory: vi.fn(), assignSavedCategories: vi.fn() });
    mockUseReportState.mockReturnValue({ vehicleReportState: null, vehicleReportRequestRef: { current: 0 }, setVehicleReportState: vi.fn(), openVehicleReport: vi.fn(), regenerateVehicleReport: vi.fn(), submitVehicleReportLookup: vi.fn(), cancelVehicleReportLookup: vi.fn() });
    mockUseRedFlagState.mockReturnValue({ redFlagState: null, setRedFlagState: vi.fn(), redFlagRequestRef: { current: 0 }, loadRedFlagState: vi.fn(), startRedFlagAnalysis: vi.fn(), cancelRedFlagAnalysis: vi.fn() });

    renderPage();

    expect(screen.getByText("No listings in this category.")).toBeTruthy();
    expect(dataState.setCurrentPage).toHaveBeenCalledWith(1);
  });

  it("renders tabs, pagination, page size, and modal close flows", () => {
    const setVehicleReportState = vi.fn();
    const setRedFlagState = vi.fn();
    const createCategoryTab = vi.fn();
    const renameActiveCategory = vi.fn();
    const deleteActiveCategory = vi.fn();
    const assignSavedCategories = vi.fn();
    const startRedFlagAnalysis = vi.fn();
    const cancelRedFlagAnalysis = vi.fn();
    const regenerateVehicleReport = vi.fn();
    const requestCurrentPosition = vi.fn();
    const openVehicleReport = vi.fn((item) => {
      setVehicleReportState({ item, loading: false, data: { status: "success" } });
    });
    const dataState = baseDataState({
      requestLoading: false,
      resultsError: "Transient warning",
      currentPage: 3,
      results: {
        totalCount: 6,
        generatedAt: "2026-03-24T12:00:00Z",
        currentCategory: "Favorites",
        categories: {
          Favorites: { label: "Favorites", count: 5, editable: true, deletable: true },
          Review: { label: "Review", count: 1, editable: false, deletable: false },
        },
        assignableCategories: [],
        items: [{ id: "listing-1", title: "BMW X1", location: "Warsaw" }],
        pagination: { page: 3, totalPages: 6, totalItems: 6 },
      },
    });
    mockUseResultsData.mockReturnValue(dataState);
    mockUseResultsGeolocation.mockReturnValue({
      geolocationState: { status: "ready" },
      locationCache: { Warsaw: { distanceKm: 5 } },
      requestCurrentPosition,
    });
    mockUseCategoryActions.mockReturnValue({
      createCategoryTab,
      renameActiveCategory,
      deleteActiveCategory,
      assignSavedCategories,
    });
    mockUseReportState.mockReturnValue({
      vehicleReportState: { item: { id: "listing-1" }, loading: false, regenerating: false, submittingLookup: false, cancellingLookup: false, data: { status: "success" } },
      vehicleReportRequestRef: { current: 0 },
      setVehicleReportState,
      openVehicleReport,
      regenerateVehicleReport,
      submitVehicleReportLookup: vi.fn(),
      cancelVehicleReportLookup: vi.fn(),
    });
    mockUseRedFlagState.mockReturnValue({
      redFlagState: { item: { id: "listing-1" }, loading: false, running: false, cancelling: false, data: { status: "success" } },
      setRedFlagState,
      redFlagRequestRef: { current: 0 },
      loadRedFlagState: vi.fn(),
      startRedFlagAnalysis,
      cancelRedFlagAnalysis,
    });

    renderPage();

    const tablist = screen.getByRole("tablist", { name: "Result categories" });
    const favoritesTab = screen.getByRole("tab", { name: "Favorites (5)", selected: true });
    const reviewTab = screen.getByRole("tab", { name: "Review (1)", selected: false });

    expect(tablist).toBeTruthy();
    fireEvent.click(reviewTab);
    favoritesTab.focus();
    fireEvent.keyDown(favoritesTab, { key: "ArrowRight" });

    fireEvent.click(screen.getByRole("button", { name: "Refresh location" }));
    fireEvent.click(screen.getByRole("button", { name: "Add category" }));
    fireEvent.click(screen.getByRole("button", { name: "Rename category" }));
    fireEvent.click(screen.getByRole("button", { name: "Delete category" }));
    fireEvent.mouseDown(screen.getByRole("combobox", { name: "Per page" }));
    fireEvent.click(screen.getByRole("option", { name: "24" }));
    fireEvent.click(screen.getByRole("button", { name: "Go to next page" }));
    fireEvent.click(screen.getByRole("button", { name: "Go to previous page" }));
    fireEvent.click(screen.getByRole("button", { name: "Go to page 6" }));
    fireEvent.click(screen.getByRole("button", { name: "open-location-listing-1" }));
    fireEvent.click(screen.getByRole("button", { name: "open-report-listing-1" }));
    fireEvent.click(screen.getByRole("button", { name: "close-location" }));
    fireEvent.click(screen.getByRole("button", { name: "close-report" }));
    fireEvent.click(screen.getByRole("button", { name: "regenerate-report" }));
    fireEvent.click(screen.getByRole("button", { name: "start-red-flags" }));
    fireEvent.click(screen.getByRole("button", { name: "cancel-red-flags" }));

    expect(screen.getByText("Transient warning")).toBeTruthy();
    expect(screen.getByText("Showing 6-6 of 6")).toBeTruthy();
    expect(dataState.setActiveCategory).toHaveBeenCalledWith("Review");
    expect(dataState.setActiveCategory).toHaveBeenCalledTimes(2);
    expect(dataState.setCurrentPage).toHaveBeenCalledWith(1);
    expect(dataState.setPageSize).toHaveBeenCalledWith(24);
    expect(dataState.setCurrentPage).toHaveBeenCalledWith(6);
    expect(createCategoryTab).toHaveBeenCalled();
    expect(renameActiveCategory).toHaveBeenCalled();
    expect(deleteActiveCategory).toHaveBeenCalled();
    expect(requestCurrentPosition).toHaveBeenCalled();
    expect(setVehicleReportState).toHaveBeenCalledWith(null);
    expect(setRedFlagState).toHaveBeenCalledWith(null);
    expect(regenerateVehicleReport).toHaveBeenCalled();
    expect(startRedFlagAnalysis).toHaveBeenCalled();
    expect(cancelRedFlagAnalysis).toHaveBeenCalled();
  });

  it("handles vehicle-report polling fetch failures", async () => {
    vi.useFakeTimers();
    try {
      const setVehicleReportState = vi.fn();
      global.fetch = vi.fn(async () => ({
        ok: false,
        status: 503,
        headers: { get: () => "application/json" },
        json: async () => ({ detail: "Upstream unavailable" }),
      }));

      mockUseResultsData.mockReturnValue(baseDataState());
      mockUseResultsGeolocation.mockReturnValue({ geolocationState: { status: "ready" }, locationCache: {}, requestCurrentPosition: vi.fn() });
      mockUseCategoryActions.mockReturnValue({ createCategoryTab: vi.fn(), renameActiveCategory: vi.fn(), deleteActiveCategory: vi.fn(), assignSavedCategories: vi.fn() });
      mockUseReportState.mockReturnValue({
        vehicleReportState: { item: { id: "listing-1" }, loading: false, regenerating: false, submittingLookup: false, cancellingLookup: false, data: { status: "running" } },
        vehicleReportRequestRef: { current: 0 },
        setVehicleReportState,
        openVehicleReport: vi.fn(),
        regenerateVehicleReport: vi.fn(),
        submitVehicleReportLookup: vi.fn(),
        cancelVehicleReportLookup: vi.fn(),
      });
      mockUseRedFlagState.mockReturnValue({
        redFlagState: null,
        setRedFlagState: vi.fn(),
        redFlagRequestRef: { current: 0 },
        loadRedFlagState: vi.fn(),
        startRedFlagAnalysis: vi.fn(),
        cancelRedFlagAnalysis: vi.fn(),
      });

      renderPage();
      await vi.advanceTimersByTimeAsync(1600);

      expect(setVehicleReportState).toHaveBeenCalled();
    } finally {
      vi.useRealTimers();
    }
  });

  it("rerenders page transitions and hides edit actions for read-only categories", () => {
    const firstState = baseDataState({
      activeCategory: "Review",
      currentPage: 5,
      results: {
        totalCount: 10,
        generatedAt: "2026-03-24T12:00:00Z",
        currentCategory: "Review",
        categories: {
          Favorites: { label: "Favorites", count: 5, editable: true, deletable: true },
          Review: { label: "Review", count: 5, editable: false, deletable: false },
        },
        assignableCategories: [],
        items: [{ id: "listing-1", title: "BMW X1", location: "Warsaw" }],
        pagination: { page: 5, totalPages: 10, totalItems: 10 },
      },
    });
    const secondState = {
      ...firstState,
      currentPage: 4,
      results: {
        ...firstState.results,
        pagination: { page: 4, totalPages: 10, totalItems: 10 },
      },
    };
    let stateIndex = 0;
    mockUseResultsData.mockImplementation(() => (stateIndex === 0 ? firstState : secondState));
    mockUseResultsGeolocation.mockReturnValue({ geolocationState: { status: "requesting" }, locationCache: {}, requestCurrentPosition: vi.fn() });
    mockUseCategoryActions.mockReturnValue({ createCategoryTab: vi.fn(), renameActiveCategory: vi.fn(), deleteActiveCategory: vi.fn(), assignSavedCategories: vi.fn() });
    mockUseReportState.mockReturnValue({ vehicleReportState: null, vehicleReportRequestRef: { current: 0 }, setVehicleReportState: vi.fn(), openVehicleReport: vi.fn(), regenerateVehicleReport: vi.fn(), submitVehicleReportLookup: vi.fn(), cancelVehicleReportLookup: vi.fn() });
    mockUseRedFlagState.mockReturnValue({ redFlagState: null, setRedFlagState: vi.fn(), redFlagRequestRef: { current: 0 }, loadRedFlagState: vi.fn(), startRedFlagAnalysis: vi.fn(), cancelRedFlagAnalysis: vi.fn() });

    const view = renderPage();
    expect(screen.queryByRole("button", { name: "Rename category" })).toBeNull();
    expect(screen.queryByRole("button", { name: "Delete category" })).toBeNull();
    expect(screen.getAllByText("…")).toHaveLength(2);

    stateIndex = 1;
    view.rerender(pageElement());

    expect(window.requestAnimationFrame).toHaveBeenCalled();
  });

  it("updates red-flag polling state and skips mismatched load requests", async () => {
    vi.useFakeTimers();
    try {
      const setRedFlagState = vi.fn();
      const loadRedFlagState = vi.fn();
      global.fetch = vi.fn(async () => ({
        ok: true,
        headers: { get: () => "application/json" },
        json: async () => ({ item: { status: "success" } }),
      }));

      mockUseResultsData.mockReturnValue(baseDataState());
      mockUseResultsGeolocation.mockReturnValue({ geolocationState: { status: "ready" }, locationCache: {}, requestCurrentPosition: vi.fn() });
      mockUseCategoryActions.mockReturnValue({ createCategoryTab: vi.fn(), renameActiveCategory: vi.fn(), deleteActiveCategory: vi.fn(), assignSavedCategories: vi.fn() });
      mockUseReportState.mockReturnValue({
        vehicleReportState: { item: { id: "listing-1" }, loading: false, regenerating: false, submittingLookup: false, cancellingLookup: false, data: { status: "success" } },
        vehicleReportRequestRef: { current: 0 },
        setVehicleReportState: vi.fn(),
        openVehicleReport: vi.fn(),
        regenerateVehicleReport: vi.fn(),
        submitVehicleReportLookup: vi.fn(),
        cancelVehicleReportLookup: vi.fn(),
      });
      mockUseRedFlagState.mockReturnValue({
        redFlagState: { item: { id: "listing-2" }, loading: false, running: true, cancelling: false, data: { status: "running" } },
        setRedFlagState,
        redFlagRequestRef: { current: 0 },
        loadRedFlagState,
        startRedFlagAnalysis: vi.fn(),
        cancelRedFlagAnalysis: vi.fn(),
      });

      renderPage();
      await vi.advanceTimersByTimeAsync(1600);

      expect(setRedFlagState).toHaveBeenCalled();
      expect(loadRedFlagState).not.toHaveBeenCalled();
    } finally {
      vi.useRealTimers();
    }
  });

  it("handles red-flag polling fetch failures", async () => {
    vi.useFakeTimers();
    try {
      const setRedFlagState = vi.fn();
      global.fetch = vi.fn(async () => ({
        ok: false,
        status: 503,
        headers: { get: () => "application/json" },
        json: async () => ({ detail: "Upstream unavailable" }),
      }));

      mockUseResultsData.mockReturnValue(baseDataState());
      mockUseResultsGeolocation.mockReturnValue({ geolocationState: { status: "ready" }, locationCache: {}, requestCurrentPosition: vi.fn() });
      mockUseCategoryActions.mockReturnValue({ createCategoryTab: vi.fn(), renameActiveCategory: vi.fn(), deleteActiveCategory: vi.fn(), assignSavedCategories: vi.fn() });
      mockUseReportState.mockReturnValue({
        vehicleReportState: null,
        vehicleReportRequestRef: { current: 0 },
        setVehicleReportState: vi.fn(),
        openVehicleReport: vi.fn(),
        regenerateVehicleReport: vi.fn(),
        submitVehicleReportLookup: vi.fn(),
        cancelVehicleReportLookup: vi.fn(),
      });
      mockUseRedFlagState.mockReturnValue({
        redFlagState: { item: { id: "listing-1" }, loading: false, running: true, cancelling: false, data: { status: "running" } },
        setRedFlagState,
        redFlagRequestRef: { current: 0 },
        loadRedFlagState: vi.fn(),
        startRedFlagAnalysis: vi.fn(),
        cancelRedFlagAnalysis: vi.fn(),
      });

      renderPage();
      await vi.advanceTimersByTimeAsync(1600);

      expect(setRedFlagState).toHaveBeenCalled();
    } finally {
      vi.useRealTimers();
    }
  });

  it("polls running report and red-flag states and updates modal helpers", async () => {
    vi.useFakeTimers();
    try {
      const setVehicleReportState = vi.fn();
      const setRedFlagState = vi.fn();
      global.fetch = vi.fn(async (path) => ({
        ok: true,
        headers: { get: () => "application/json" },
        json: async () => ({
          item: String(path).includes("red-flags")
            ? { status: "success" }
            : { status: "success", report: { ok: true } },
        }),
      }));

      mockUseResultsData.mockReturnValue(baseDataState());
      mockUseResultsGeolocation.mockReturnValue({ geolocationState: { status: "ready" }, locationCache: {}, requestCurrentPosition: vi.fn() });
      mockUseCategoryActions.mockReturnValue({ createCategoryTab: vi.fn(), renameActiveCategory: vi.fn(), deleteActiveCategory: vi.fn(), assignSavedCategories: vi.fn() });
      mockUseReportState.mockReturnValue({
        vehicleReportState: { item: { id: "listing-1" }, loading: false, regenerating: false, submittingLookup: false, cancellingLookup: false, data: { status: "running" } },
        vehicleReportRequestRef: { current: 0 },
        setVehicleReportState,
        openVehicleReport: vi.fn(),
        regenerateVehicleReport: vi.fn(),
        submitVehicleReportLookup: vi.fn(),
        cancelVehicleReportLookup: vi.fn(),
      });
      mockUseRedFlagState.mockReturnValue({
        redFlagState: { item: { id: "listing-1" }, loading: false, running: true, cancelling: false, data: { status: "running" } },
        setRedFlagState,
        redFlagRequestRef: { current: 0 },
        loadRedFlagState: vi.fn(),
        startRedFlagAnalysis: vi.fn(),
        cancelRedFlagAnalysis: vi.fn(),
      });

      renderPage();
      await vi.advanceTimersByTimeAsync(1600);

      expect(setVehicleReportState).toHaveBeenCalled();
      expect(setRedFlagState).toHaveBeenCalled();
    } finally {
      vi.useRealTimers();
    }
  });
});
