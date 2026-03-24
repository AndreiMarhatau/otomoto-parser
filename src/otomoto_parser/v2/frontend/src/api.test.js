import { afterEach, describe, expect, it, vi } from "vitest";

import { api } from "./api";

describe("api", () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("returns parsed JSON for successful JSON responses", async () => {
    global.fetch = vi.fn(async () => ({
      ok: true,
      headers: { get: () => "application/json; charset=utf-8" },
      json: async () => ({ item: 1 }),
    }));

    await expect(api("/api/example")).resolves.toEqual({ item: 1 });
    expect(global.fetch).toHaveBeenCalledWith(
      "/api/example",
      expect.objectContaining({ headers: { "Content-Type": "application/json" } }),
    );
  });

  it("returns the raw response for non-JSON success payloads", async () => {
    const response = {
      ok: true,
      headers: { get: () => "text/plain" },
    };
    global.fetch = vi.fn(async () => response);

    await expect(api("/api/download")).resolves.toBe(response);
  });

  it("surfaces API error details from JSON payloads", async () => {
    global.fetch = vi.fn(async () => ({
      ok: false,
      status: 422,
      headers: { get: () => "application/json" },
      json: async () => ({ detail: "Bad request payload" }),
    }));

    await expect(api("/api/example")).rejects.toThrow("Bad request payload");
  });

  it("falls back to status text when an error payload is not JSON", async () => {
    global.fetch = vi.fn(async () => ({
      ok: false,
      status: 503,
      headers: { get: () => "text/plain" },
      json: async () => {
        throw new Error("invalid json");
      },
    }));

    await expect(api("/api/example")).rejects.toThrow("Request failed with status 503");
  });
});
