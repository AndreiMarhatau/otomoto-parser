// @vitest-environment jsdom
import { cleanup, fireEvent, render, waitFor } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import React from "react";
import { api } from "./api";
import { accessRequest, useAccessActivity } from "./access-session";
vi.mock("./api", () => ({ api: vi.fn() }));
afterEach(() => { cleanup(); vi.restoreAllMocks(); });
it("serializes logout behind an in-flight renewal", async () => {
  let release;
  api.mockImplementationOnce(() => new Promise(resolve => { release = resolve; })).mockResolvedValue({});
  const renew = accessRequest({ action: "renew" });
  await Promise.resolve();
  const logout = accessRequest({ action: "logout" });
  expect(api).toHaveBeenCalledTimes(1);
  release({});
  await renew; await logout;
  expect(JSON.parse(api.mock.calls[1][1].body).action).toBe("logout");
});
it("renews on initial load and throttled activity, never a passive timer", async () => {
  api.mockReset(); api.mockResolvedValue({});
  let now = 2000000;
  vi.spyOn(Date, "now").mockImplementation(() => now);
  function Harness() { useAccessActivity(); return <button>Work</button>; }
  render(<Harness />);
  await waitFor(() => expect(api).toHaveBeenCalledTimes(1));
  fireEvent.pointerDown(window);
  await Promise.resolve();
  expect(api).toHaveBeenCalledTimes(1);
  now += 61000;
  fireEvent.keyDown(window, { key: "a" });
  await waitFor(() => expect(api).toHaveBeenCalledTimes(2));
  expect(api.mock.calls.every(([, options]) => JSON.parse(options.body).action === "renew")).toBe(true);
});
