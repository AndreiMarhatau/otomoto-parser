// @vitest-environment jsdom

import React from "react";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { useCategoryActions } from "./use-category-actions";
import { useRedFlagState } from "./use-red-flag-state";
import { useReportState } from "./use-report-state";
import { jsonResponse } from "./test-helpers";

function CategoryActionsHarness({ createCategory = async () => ({ key: "custom", label: "Custom" }) }) {
  const [activeCategory, setActiveCategory] = React.useState("Favorites");
  const [currentPage, setCurrentPage] = React.useState(3);
  const [resultsError, setResultsError] = React.useState(null);
  const [busyByListing, setBusyByListing] = React.useState({});
  const [reloads, setReloads] = React.useState(0);
  const actions = useCategoryActions({
    requestId: "req-1",
    results: {
      categories: {
        Favorites: { label: "Favorites", editable: true, deletable: true },
      },
    },
    activeCategory,
    setActiveCategory,
    setCurrentPage,
    bumpResultsReload: () => setReloads((value) => value + 1),
    setResultsError,
    createCategory,
    setCategoryBusyByListing: setBusyByListing,
  });

  return (
    <div>
      <button type="button" onClick={() => void actions.createCategoryTab()}>create-tab</button>
      <button type="button" onClick={() => void actions.renameActiveCategory()}>rename-tab</button>
      <button type="button" onClick={() => void actions.deleteActiveCategory()}>delete-tab</button>
      <button type="button" onClick={() => void actions.assignSavedCategories({ id: "listing-1" }, ["Favorites"])}>assign-tab</button>
      <p>{activeCategory}</p>
      <p>{currentPage}</p>
      <p>{resultsError || "no-error"}</p>
      <p>{String(Boolean(busyByListing["listing-1"]))}</p>
      <p>{reloads}</p>
    </div>
  );
}

function ReportStateHarness() {
  const [redFlagState, setRedFlagState] = React.useState(null);
  const [updated, setUpdated] = React.useState([]);
  const redFlagRequestRef = React.useRef(0);
  const state = useReportState({
    requestId: "req-1",
    loadRedFlagState: async (item) => {
      setRedFlagState({ item, data: { status: "idle" } });
    },
    updateVehicleReportResultItem: (...args) => setUpdated((current) => [...current, args]),
    redFlagRequestRef,
    setRedFlagState,
  });
  const item = { id: "listing-1", title: "BMW X1" };
  return (
    <div>
      <button type="button" onClick={() => void state.openVehicleReport(item)}>open-report</button>
      <button type="button" onClick={() => void state.regenerateVehicleReport()}>regenerate-report</button>
      <button type="button" onClick={() => void state.submitVehicleReportLookup({ registrationNumber: "WW2222C" })}>lookup-report</button>
      <button type="button" onClick={() => void state.cancelVehicleReportLookup()}>cancel-report</button>
      <p>{state.vehicleReportState?.data?.status || state.vehicleReportState?.error || "empty"}</p>
      <p>{updated.length}</p>
      <p>{redFlagState?.data?.status || "no-red-flags"}</p>
    </div>
  );
}

function ReportStateRaceHarness() {
  const [redFlagState, setRedFlagState] = React.useState(null);
  const [updated, setUpdated] = React.useState([]);
  const redFlagRequestRef = React.useRef(0);
  const state = useReportState({
    requestId: "req-1",
    loadRedFlagState: async (item) => {
      setRedFlagState({ item, data: { status: "idle" } });
    },
    updateVehicleReportResultItem: (...args) => setUpdated((current) => [...current, args]),
    redFlagRequestRef,
    setRedFlagState,
  });
  return (
    <div>
      <button type="button" onClick={() => void state.openVehicleReport({ id: "listing-1", title: "One" })}>open-report-1</button>
      <button type="button" onClick={() => void state.openVehicleReport({ id: "listing-2", title: "Two" })}>open-report-2</button>
      <p>{state.vehicleReportState?.item?.id || state.vehicleReportState?.error || "empty"}</p>
      <p>{updated.length}</p>
      <p>{redFlagState?.item?.id || "no-red-flags"}</p>
    </div>
  );
}

function RedFlagStateHarness() {
  const state = useRedFlagState("req-1");
  React.useEffect(() => {
    state.setRedFlagState({ item: { id: "listing-1" }, loading: false, running: false, cancelling: false, error: null, data: { status: "idle" } });
  }, []);
  return (
    <div>
      <button type="button" onClick={() => void state.loadRedFlagState({ id: "listing-1" })}>load-red-flags</button>
      <button type="button" onClick={() => void state.startRedFlagAnalysis()}>start-red-flags</button>
      <button type="button" onClick={() => void state.cancelRedFlagAnalysis()}>cancel-red-flags</button>
      <p>{state.redFlagState?.data?.status || state.redFlagState?.error || "empty"}</p>
    </div>
  );
}

describe("state hooks", () => {
  beforeEach(() => {
    window.prompt = vi.fn(() => "Renamed");
    window.confirm = vi.fn(() => true);
  });

  afterEach(() => {
    cleanup();
    vi.restoreAllMocks();
  });

  it("runs category actions and handles API calls", async () => {
    global.fetch = vi.fn(async (path, options = {}) => {
      if (path === "/api/requests/req-1/categories/Favorites" && options.method === "PATCH") {
        return jsonResponse({ item: { key: "Favorites" } });
      }
      if (path === "/api/requests/req-1/categories/Favorites" && options.method === "DELETE") {
        return jsonResponse({ ok: true });
      }
      if (path === "/api/requests/req-1/listings/listing-1/categories" && options.method === "PUT") {
        return jsonResponse({ ok: true });
      }
      throw new Error(`Unhandled fetch path: ${path}`);
    });

    render(<CategoryActionsHarness />);

    fireEvent.click(screen.getByText("rename-tab"));
    fireEvent.click(screen.getByText("delete-tab"));
    fireEvent.click(screen.getByText("assign-tab"));
    fireEvent.click(screen.getByText("create-tab"));

    await waitFor(() => {
      expect(global.fetch).toHaveBeenCalledWith(
        "/api/requests/req-1/categories/Favorites",
        expect.objectContaining({ method: "PATCH" }),
      );
      expect(global.fetch).toHaveBeenCalledWith(
        "/api/requests/req-1/categories/Favorites",
        expect.objectContaining({ method: "DELETE" }),
      );
      expect(global.fetch).toHaveBeenCalledWith(
        "/api/requests/req-1/listings/listing-1/categories",
        expect.objectContaining({ method: "PUT" }),
      );
    });
  });

  it("surfaces category-action failures and null category creation", async () => {
    global.fetch = vi.fn(async () => {
      throw new Error("category failure");
    });

    render(<CategoryActionsHarness createCategory={async () => null} />);

    fireEvent.click(screen.getByText("create-tab"));
    expect(screen.getByText("Favorites")).toBeTruthy();

    fireEvent.click(screen.getByText("rename-tab"));
    fireEvent.click(screen.getByText("delete-tab"));
    fireEvent.click(screen.getByText("assign-tab"));

    await waitFor(() => {
      expect(screen.getByText("category failure")).toBeTruthy();
    });
  });

  it("runs vehicle report actions and red-flag actions", async () => {
    global.fetch = vi.fn(async (path, options = {}) => {
      if (path === "/api/requests/req-1/listings/listing-1/vehicle-report") {
        return jsonResponse({ item: { status: "success", identity: { vin: "VIN123" } } });
      }
      if (path === "/api/requests/req-1/listings/listing-1/vehicle-report/regenerate" && options.method === "POST") {
        return jsonResponse({ item: { status: "success" } });
      }
      if (path === "/api/requests/req-1/listings/listing-1/vehicle-report/lookup" && options.method === "POST") {
        return jsonResponse({ item: { status: "running" } });
      }
      if (path === "/api/requests/req-1/listings/listing-1/vehicle-report/lookup/cancel" && options.method === "POST") {
        return jsonResponse({ item: { status: "cancelled" } });
      }
      if (path === "/api/requests/req-1/listings/listing-1/red-flags") {
        return jsonResponse({ item: { status: options.method === "POST" ? "running" : "success" } });
      }
      if (path === "/api/requests/req-1/listings/listing-1/red-flags/cancel" && options.method === "POST") {
        return jsonResponse({ item: { status: "cancelled" } });
      }
      throw new Error(`Unhandled fetch path: ${path}`);
    });

    render(
      <>
        <ReportStateHarness />
        <RedFlagStateHarness />
      </>,
    );

    fireEvent.click(screen.getByText("open-report"));
    await screen.findByText("success");

    fireEvent.click(screen.getByText("regenerate-report"));
    fireEvent.click(screen.getByText("lookup-report"));
    fireEvent.click(screen.getByText("cancel-report"));
    fireEvent.click(screen.getByText("load-red-flags"));
    fireEvent.click(screen.getByText("start-red-flags"));
    fireEvent.click(screen.getByText("cancel-red-flags"));

    await waitFor(() => {
      expect(global.fetch).toHaveBeenCalledWith(
        "/api/requests/req-1/listings/listing-1/vehicle-report/regenerate",
        expect.objectContaining({ method: "POST" }),
      );
      expect(global.fetch).toHaveBeenCalledWith(
        "/api/requests/req-1/listings/listing-1/red-flags/cancel",
        expect.objectContaining({ method: "POST" }),
      );
    });
  });

  it("keeps hook state consistent when report and red-flag requests fail", async () => {
    global.fetch = vi.fn(async (path) => {
      if (String(path).includes("/vehicle-report") || String(path).includes("/red-flags")) {
        throw new Error("network down");
      }
      throw new Error(`Unhandled fetch path: ${path}`);
    });

    render(
      <>
        <ReportStateHarness />
        <RedFlagStateHarness />
      </>,
    );

    fireEvent.click(screen.getByText("open-report"));
    fireEvent.click(screen.getByText("start-red-flags"));

    await waitFor(() => {
      expect(screen.getAllByText("network down").length).toBeGreaterThan(0);
    });
  });

  it("ignores report actions when no listing is active", async () => {
    global.fetch = vi.fn();

    render(<ReportStateHarness />);

    fireEvent.click(screen.getByText("regenerate-report"));
    fireEvent.click(screen.getByText("lookup-report"));
    fireEvent.click(screen.getByText("cancel-report"));

    expect(global.fetch).not.toHaveBeenCalled();
  });

  it("ignores stale report responses and preserves the most recent selection", async () => {
    const resolvers = {};
    global.fetch = vi.fn((path) => {
      if (path === "/api/requests/req-1/listings/listing-1/vehicle-report") {
        return new Promise((resolve) => {
          resolvers.first = resolve;
        });
      }
      if (path === "/api/requests/req-1/listings/listing-2/vehicle-report") {
        return new Promise((resolve) => {
          resolvers.second = resolve;
        });
      }
      throw new Error(`Unhandled fetch path: ${path}`);
    });

    render(<ReportStateRaceHarness />);

    fireEvent.click(screen.getByText("open-report-1"));
    fireEvent.click(screen.getByText("open-report-2"));

    resolvers.first(jsonResponse({ item: { status: "success", identity: { vin: "VIN-1" } } }));
    resolvers.second(jsonResponse({ item: { status: "success", identity: { vin: "VIN-2" } } }));

    await waitFor(() => {
      expect(screen.getAllByText("listing-2")).toHaveLength(2);
    });
    expect(screen.getByText("1")).toBeTruthy();
  });
});
