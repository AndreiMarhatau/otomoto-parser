// @vitest-environment jsdom

import React from "react";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes, useNavigate } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import { RequestDetailPage } from "./request-detail-page";
import { jsonResponse } from "./test-helpers";

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
    expect((await screen.findAllByText("Request one ready")).length).toBeGreaterThan(0);

    fireEvent.click(screen.getByRole("button", { name: "Open request 2" }));

    expect(await screen.findByText("Request req-2")).toBeTruthy();
    expect((await screen.findAllByText("Request two ready")).length).toBeGreaterThan(0);
    expect(fetchMock).toHaveBeenCalledWith("/api/requests/req-2", expect.any(Object));
  });

  it("triggers rerun actions and deletes completed requests", async () => {
    window.confirm = vi.fn(() => true);
    window.alert = vi.fn();
    const fetchMock = vi.fn(async (path, options = {}) => {
      if (path === "/api/requests/req-1" && (!options.method || options.method === "GET")) {
        return jsonResponse({
          item: {
            id: "req-1",
            sourceUrl: "https://example.invalid/req-1",
            status: "ready",
            pagesCompleted: 1,
            resultsWritten: 10,
            resultsReady: true,
            excelReady: true,
            progressMessage: "Request one ready",
            error: null,
          },
        });
      }
      if (path === "/api/requests/req-1/resume" && options.method === "POST") {
        return jsonResponse({ ok: true });
      }
      if (path === "/api/requests/req-1/redo" && options.method === "POST") {
        return jsonResponse({ ok: true });
      }
      if (path === "/api/requests/req-1" && options.method === "DELETE") {
        return jsonResponse({ ok: true });
      }
      throw new Error(`Unhandled fetch path: ${path}`);
    });
    global.fetch = fetchMock;

    render(
      <MemoryRouter initialEntries={["/requests/req-1"]}>
        <Routes>
          <Route path="/" element={<p>Requests home</p>} />
          <Route path="/requests/:requestId" element={<RequestDetailPage />} />
        </Routes>
      </MemoryRouter>,
    );

    await screen.findByText("Request req-1");
    fireEvent.click(screen.getByRole("button", { name: "Resume and gather new" }));
    fireEvent.click(screen.getByRole("button", { name: "Redo from scratch" }));
    expect(screen.getByRole("link", { name: "https://example.invalid/req-1" })).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Delete request" }));

    expect(await screen.findByText("Requests home")).toBeTruthy();
    expect(fetchMock).toHaveBeenCalledWith("/api/requests/req-1/resume", expect.objectContaining({ method: "POST" }));
    expect(fetchMock).toHaveBeenCalledWith("/api/requests/req-1/redo", expect.objectContaining({ method: "POST" }));
    expect(fetchMock).toHaveBeenCalledWith("/api/requests/req-1", expect.objectContaining({ method: "DELETE" }));
  });

  it("renders loading and error states and handles running and failed deletes", async () => {
    let requestCount = 0;
    window.confirm = vi.fn(() => true);
    window.alert = vi.fn();
    const fetchMock = vi.fn(async (path, options = {}) => {
      if (path === "/api/requests/req-1" && (!options.method || options.method === "GET")) {
        requestCount += 1;
        if (requestCount === 1) {
          return new Promise(() => {});
        }
        if (requestCount === 2) {
          throw new Error("request exploded");
        }
        if (requestCount === 3) {
          return jsonResponse({
            item: {
              id: "req-1",
              sourceUrl: "https://example.invalid/req-1",
              status: "running",
              pagesCompleted: 1,
              resultsWritten: 10,
              resultsReady: false,
              excelReady: false,
              progressMessage: "Still running",
              error: "Request error",
            },
          });
        }
        return jsonResponse({
          item: {
            id: "req-1",
            sourceUrl: "https://example.invalid/req-1",
            status: "ready",
            pagesCompleted: 1,
            resultsWritten: 10,
            resultsReady: true,
            excelReady: false,
            progressMessage: "Ready to delete",
            error: null,
          },
        });
      }
      if (path === "/api/requests/req-1" && options.method === "DELETE") {
        throw new Error("delete exploded");
      }
      throw new Error(`Unhandled fetch path: ${path}`);
    });
    global.fetch = fetchMock;

    const loadingView = render(
      <MemoryRouter initialEntries={["/requests/req-1"]}>
        <Routes>
          <Route path="/requests/:requestId" element={<RequestDetailPage />} />
        </Routes>
      </MemoryRouter>,
    );
    expect(screen.getByText("Loading request...")).toBeTruthy();
    loadingView.unmount();

    render(
      <MemoryRouter initialEntries={["/requests/req-1"]}>
        <Routes>
          <Route path="/requests/:requestId" element={<RequestDetailPage />} />
        </Routes>
      </MemoryRouter>,
    );
    expect(await screen.findByText("request exploded")).toBeTruthy();
    cleanup();

    render(
      <MemoryRouter initialEntries={["/requests/req-1"]}>
        <Routes>
          <Route path="/requests/:requestId" element={<RequestDetailPage />} />
        </Routes>
      </MemoryRouter>,
    );

    expect(await screen.findByText("Request req-1")).toBeTruthy();
    expect(screen.getByText("Request error")).toBeTruthy();
    expect(screen.getByRole("button", { name: "Delete request" })).toHaveProperty("disabled", true);
    fireEvent.click(screen.getByRole("button", { name: "Delete request" }));
    expect(window.alert).not.toHaveBeenCalled();
    expect(window.confirm).not.toHaveBeenCalled();
    cleanup();

    render(
      <MemoryRouter initialEntries={["/requests/req-1"]}>
        <Routes>
          <Route path="/" element={<p>Requests home</p>} />
          <Route path="/requests/:requestId" element={<RequestDetailPage />} />
        </Routes>
      </MemoryRouter>,
    );
    expect((await screen.findAllByText("Ready to delete")).length).toBeGreaterThan(0);
    fireEvent.click(screen.getByRole("button", { name: "Delete request" }));
    await screen.findByText("Request req-1");
    expect(window.confirm).toHaveBeenCalledWith("Remove this request and its stored files?");
    expect(window.alert).toHaveBeenCalledWith("delete exploded");
  });

  it("renders the compact detail actions and metrics", async () => {
    global.fetch = vi.fn(async (path, options = {}) => {
      if (path === "/api/requests/req-1" && (!options.method || options.method === "GET")) {
        return jsonResponse({
          item: {
            id: "req-1",
            sourceUrl: "https://example.invalid/req-1",
            status: "ready",
            pagesCompleted: 1,
            resultsWritten: 10,
            resultsReady: true,
            excelReady: true,
            progressMessage: "Ready to inspect",
            error: null,
          },
        });
      }
      throw new Error(`Unhandled fetch path: ${path}`);
    });

    render(
      <MemoryRouter initialEntries={["/requests/req-1"]}>
        <Routes>
          <Route path="/requests/:requestId" element={<RequestDetailPage />} />
        </Routes>
      </MemoryRouter>,
    );

    expect(await screen.findByText("Request req-1")).toBeTruthy();
    expect(screen.getByRole("button", { name: "Resume and gather new" })).toBeTruthy();
    expect(screen.getByRole("button", { name: "Redo from scratch" })).toBeTruthy();
    expect(screen.getByRole("link", { name: "Open results" })).toBeTruthy();
    expect(screen.getByRole("link", { name: "Download Excel" })).toBeTruthy();
  });
});
