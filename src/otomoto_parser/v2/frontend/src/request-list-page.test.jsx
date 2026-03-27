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

    fireEvent.click(await screen.findByRole("button", { name: /new request/i }));
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

    fireEvent.click(await screen.findByRole("button", { name: /new request/i }));
    const textarea = await screen.findByPlaceholderText("https://www.otomoto.pl/osobowe/...");
    fireEvent.change(textarea, { target: { value: "bad-url" } });
    fireEvent.click(screen.getByRole("button", { name: "Create request" }));

    expect(await screen.findByText("URL is invalid")).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Cancel" }));

    const row = await screen.findByRole("button", { name: /Request req-1/ });
    expect(row).toBeTruthy();
    row.focus();
    fireEvent.click(row);

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

    const row = screen.getByRole("button", { name: /Request req-1/ });
    fireEvent.click(row);
    expect(await screen.findByText("Request detail route")).toBeTruthy();
  });

  it("renders malformed, relative, and empty source URLs without crashing", async () => {
    global.fetch = vi.fn(async (path, options = {}) => {
      if (path === "/api/requests" && (!options.method || options.method === "GET")) {
        return jsonResponse({
          items: [
            {
              id: "req-absolute",
              sourceUrl: "https://example.invalid/req-absolute",
              status: "ready",
              progressMessage: "Ready",
              resultsWritten: 1,
              pagesCompleted: 1,
              createdAt: "2026-03-24T12:00:00Z",
            },
            {
              id: "req-relative",
              sourceUrl: "/relative/path",
              status: "ready",
              progressMessage: "Relative",
              resultsWritten: 2,
              pagesCompleted: 1,
              createdAt: "2026-03-24T12:00:00Z",
            },
            {
              id: "req-invalid",
              sourceUrl: "::::",
              status: "ready",
              progressMessage: "Invalid",
              resultsWritten: 3,
              pagesCompleted: 1,
              createdAt: "2026-03-24T12:00:00Z",
            },
            {
              id: "req-empty",
              sourceUrl: "",
              status: "ready",
              progressMessage: "Empty",
              resultsWritten: 4,
              pagesCompleted: 1,
              createdAt: "2026-03-24T12:00:00Z",
            },
          ],
        });
      }
      throw new Error(`Unhandled fetch path: ${path}`);
    });

    renderRequestListPage();

    expect(await screen.findByText("Request req-absolute")).toBeTruthy();
    expect(screen.getByText("example.invalid")).toBeTruthy();
    expect(screen.getByText("Relative URL")).toBeTruthy();
    expect(screen.getByText("Invalid URL")).toBeTruthy();
    expect(screen.getByText("No source")).toBeTruthy();
    expect(screen.getByText("No source URL")).toBeTruthy();
    expect(screen.getByRole("link", { name: "/relative/path" }).getAttribute("href")).toBe("/relative/path");
    expect(screen.getByRole("link", { name: "https://example.invalid/req-absolute" }).getAttribute("href")).toBe("https://example.invalid/req-absolute");
    expect(screen.queryByRole("link", { name: "::::" })).toBeNull();
  });

  it("renders request rows and create dialog actions", async () => {
    global.fetch = vi.fn(async (path, options = {}) => {
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
      throw new Error(`Unhandled fetch path: ${path}`);
    });

    renderRequestListPage();

    expect(await screen.findByText("Request req-1")).toBeTruthy();
    expect(screen.getByText(/5 listings/)).toBeTruthy();

    fireEvent.click(screen.getByRole("button", { name: /new request/i }));

    expect(screen.getByPlaceholderText("https://www.otomoto.pl/osobowe/...")).toBeTruthy();
    expect(screen.getByRole("button", { name: "Create request" })).toBeTruthy();
  });

  it("adds dialog semantics, focuses the textarea, and returns focus to the opener on escape close", async () => {
    global.fetch = vi.fn(async (path, options = {}) => {
      if (path === "/api/requests" && (!options.method || options.method === "GET")) {
        return jsonResponse({ items: [] });
      }
      throw new Error(`Unhandled fetch path: ${path}`);
    });

    renderRequestListPage();

    const opener = await screen.findByRole("button", { name: /new request/i });
    opener.focus();
    fireEvent.click(opener);

    const dialog = screen.getByRole("dialog", { name: "Create request" });
    expect(dialog.getAttribute("aria-modal")).toBe("true");
    expect(screen.getByPlaceholderText("https://www.otomoto.pl/osobowe/...")).toBe(document.activeElement);

    fireEvent.keyDown(dialog, { key: "Escape" });

    await waitFor(() => {
      expect(screen.queryByRole("dialog", { name: "Create request" })).toBeNull();
    });
  });

  it("renders the expected focusable controls inside the dialog", async () => {
    global.fetch = vi.fn(async (path, options = {}) => {
      if (path === "/api/requests" && (!options.method || options.method === "GET")) {
        return jsonResponse({ items: [] });
      }
      throw new Error(`Unhandled fetch path: ${path}`);
    });

    renderRequestListPage();

    fireEvent.click(await screen.findByRole("button", { name: /new request/i }));

    const textarea = screen.getByPlaceholderText("https://www.otomoto.pl/osobowe/...");
    const closeButton = screen.getByRole("button", { name: "Close dialog" });
    const createButton = screen.getByRole("button", { name: "Create request" });
    const cancelButton = screen.getByRole("button", { name: "Cancel" });

    expect(textarea).toBeTruthy();
    expect(closeButton).toBeTruthy();
    expect(createButton).toBeTruthy();
    expect(cancelButton).toBeTruthy();
  });

  it("closes on backdrop click when idle and returns focus to the opener", async () => {
    global.fetch = vi.fn(async (path, options = {}) => {
      if (path === "/api/requests" && (!options.method || options.method === "GET")) {
        return jsonResponse({ items: [] });
      }
      throw new Error(`Unhandled fetch path: ${path}`);
    });

    renderRequestListPage();

    const opener = await screen.findByRole("button", { name: /new request/i });
    fireEvent.click(opener);
    fireEvent.mouseDown(document.querySelector(".MuiBackdrop-root"));
    fireEvent.click(document.querySelector(".MuiBackdrop-root"));

    await waitFor(() => {
      expect(screen.queryByRole("dialog", { name: "Create request" })).toBeNull();
    });
  });

  it("does not dismiss on escape or backdrop while create request is in flight and preserves the error state", async () => {
    let rejectSubmit;
    const submitPromise = new Promise((_, reject) => {
      rejectSubmit = reject;
    });

    global.fetch = vi.fn(async (path, options = {}) => {
      if (path === "/api/requests" && (!options.method || options.method === "GET")) {
        return jsonResponse({ items: [] });
      }
      if (path === "/api/requests" && options.method === "POST") {
        return submitPromise;
      }
      throw new Error(`Unhandled fetch path: ${path}`);
    });

    renderRequestListPage();

    fireEvent.click(await screen.findByRole("button", { name: /new request/i }));
    const textarea = screen.getByPlaceholderText("https://www.otomoto.pl/osobowe/...");
    fireEvent.change(textarea, { target: { value: "https://example.invalid/search" } });
    fireEvent.click(screen.getByRole("button", { name: "Create request" }));

    expect(screen.getByRole("button", { name: "Creating..." })).toHaveProperty("disabled", true);

    fireEvent.keyDown(window, { key: "Escape" });
    fireEvent.mouseDown(document.querySelector(".MuiBackdrop-root"));
    fireEvent.click(document.querySelector(".MuiBackdrop-root"));
    expect(screen.getByRole("dialog", { name: "Create request" })).toBeTruthy();

    rejectSubmit(new Error("submit failed"));

    expect(await screen.findByText("submit failed")).toBeTruthy();
    expect(screen.getByRole("dialog", { name: "Create request" })).toBeTruthy();
    expect(screen.getByPlaceholderText("https://www.otomoto.pl/osobowe/...")).toHaveProperty("value", "https://example.invalid/search");
  });
});
