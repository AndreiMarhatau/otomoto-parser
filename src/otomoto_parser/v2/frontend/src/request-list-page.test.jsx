// @vitest-environment jsdom

import React from "react";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { RequestListPage } from "./request-list-page";
import { jsonResponse } from "./test-helpers";

function renderRequestListPage() {
  return render(
    <MemoryRouter initialEntries={["/"]}>
      <Routes>
        <Route path="/" element={<RequestListPage />} />
        <Route path="/requests/:requestId" element={<p>Request detail route</p>} />
      </Routes>
    </MemoryRouter>,
  );
}

describe("RequestListPage", () => {
  beforeEach(() => {
    window.alert = vi.fn();
    window.confirm = vi.fn(() => true);
  });

  afterEach(() => {
    cleanup();
    vi.restoreAllMocks();
  });

  it("creates a request and navigates to the detail page", async () => {
    global.fetch = vi.fn(async (path, options = {}) => {
      if (path === "/api/requests" && (!options.method || options.method === "GET")) {
        return jsonResponse({ items: [] });
      }
      if (path === "/api/requests" && options.method === "POST") {
        expect(JSON.parse(options.body)).toEqual({ url: "https://example.invalid/search" });
        return jsonResponse({ item: { id: "req-2" } });
      }
      throw new Error(`Unhandled fetch path: ${path}`);
    });

    renderRequestListPage();

    fireEvent.change(await screen.findByPlaceholderText("https://www.otomoto.pl/osobowe/..."), {
      target: { value: "https://example.invalid/search" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Create request" }));

    expect(await screen.findByText("Request detail route")).toBeTruthy();
  });

  it("blocks deletion for in-progress requests and reloads after confirmed delete", async () => {
    global.fetch = vi.fn(async (path, options = {}) => {
      if (path === "/api/requests" && (!options.method || options.method === "GET")) {
        return jsonResponse({
          items: [
            {
              id: "req-running",
              sourceUrl: "https://example.invalid/running",
              status: "running",
              progressMessage: "Running",
              resultsWritten: 2,
              pagesCompleted: 1,
              createdAt: "2026-03-24T12:00:00Z",
            },
            {
              id: "req-ready",
              sourceUrl: "https://example.invalid/ready",
              status: "ready",
              progressMessage: "Ready",
              resultsWritten: 5,
              pagesCompleted: 3,
              createdAt: "2026-03-24T12:00:00Z",
            },
          ],
        });
      }
      if (path === "/api/requests/req-ready" && options.method === "DELETE") {
        return jsonResponse({ ok: true });
      }
      throw new Error(`Unhandled fetch path: ${path}`);
    });

    renderRequestListPage();

    const deleteButtons = await screen.findAllByRole("button", { name: "Delete request" });
    expect(deleteButtons[0]).toHaveProperty("disabled", true);

    fireEvent.click(deleteButtons[1]);

    await waitFor(() => {
      expect(global.fetch).toHaveBeenCalledWith("/api/requests/req-ready", expect.objectContaining({ method: "DELETE" }));
    });
    expect(window.confirm).toHaveBeenCalledWith("Remove this request and its stored files?");
    expect(window.alert).not.toHaveBeenCalled();
  });

  it("shows submit errors and supports keyboard navigation on rows", async () => {
    const fetchMock = vi.fn(async (path, options = {}) => {
      if (path === "/api/requests" && (!options.method || options.method === "GET")) {
        return jsonResponse({
          items: [
            {
              id: "req-1",
              sourceUrl: "https://example.invalid/req-1",
              status: "ready",
              progressMessage: "Ready",
              resultsWritten: 5,
              pagesCompleted: 3,
              createdAt: "2026-03-24T12:00:00Z",
            },
          ],
        });
      }
      if (path === "/api/requests" && options.method === "POST") {
        return {
          ok: false,
          status: 422,
          headers: { get: () => "application/json" },
          json: async () => ({ detail: "URL is invalid" }),
        };
      }
      throw new Error(`Unhandled fetch path: ${path}`);
    });
    global.fetch = fetchMock;

    renderRequestListPage();

    const textarea = await screen.findByPlaceholderText("https://www.otomoto.pl/osobowe/...");
    fireEvent.change(textarea, { target: { value: "bad-url" } });
    fireEvent.click(screen.getByRole("button", { name: "Create request" }));

    expect(await screen.findByText("URL is invalid")).toBeTruthy();

    const row = screen.getByText("Request req-1").closest('[role="link"]');
    expect(row).toBeTruthy();
    row.focus();
    fireEvent.keyDown(row, { key: "Enter" });

    expect(await screen.findByText("Request detail route")).toBeTruthy();
  });

  it("refreshes, ignores cancelled deletes, alerts on delete failures, and supports space-key navigation", async () => {
    let listCalls = 0;
    window.confirm = vi.fn(() => false);
    window.alert = vi.fn();
    global.fetch = vi.fn(async (path, options = {}) => {
      if (path === "/api/requests" && (!options.method || options.method === "GET")) {
        listCalls += 1;
        return jsonResponse({
          items: [
            {
              id: "req-1",
              sourceUrl: "https://example.invalid/req-1",
              status: "ready",
              progressMessage: "Ready",
              resultsWritten: 5,
              pagesCompleted: 3,
              createdAt: "2026-03-24T12:00:00Z",
            },
          ],
        });
      }
      if (path === "/api/requests/req-1" && options.method === "DELETE") {
        throw new Error("delete failed");
      }
      throw new Error(`Unhandled fetch path: ${path}`);
    });

    renderRequestListPage();

    await screen.findByText("Request req-1");
    fireEvent.click(screen.getByRole("button", { name: "Refresh request list" }));
    await waitFor(() => {
      expect(listCalls).toBeGreaterThan(1);
    });

    fireEvent.click(screen.getByRole("button", { name: "Delete request" }));
    expect(window.confirm).toHaveBeenCalled();
    expect(global.fetch).not.toHaveBeenCalledWith("/api/requests/req-1", expect.objectContaining({ method: "DELETE" }));

    window.confirm = vi.fn(() => true);
    fireEvent.click(screen.getByRole("button", { name: "Delete request" }));
    await waitFor(() => {
      expect(window.alert).toHaveBeenCalledWith("delete failed");
    });

    const row = screen.getByText("Request req-1").closest('[role="link"]');
    fireEvent.keyDown(row, { key: " " });
    expect(await screen.findByText("Request detail route")).toBeTruthy();
  });
});
