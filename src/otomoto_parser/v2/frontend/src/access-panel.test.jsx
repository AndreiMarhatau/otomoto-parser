// @vitest-environment jsdom
import React from "react";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import { AccessPanel } from "./access-panel";
afterEach(() => { cleanup(); vi.restoreAllMocks(); });
function setup(status) {
  global.fetch = vi.fn(async () => ({ ok: true, headers: new Headers({ "content-type": "application/json" }), json: async () => status }));
  render(<AccessPanel />);
}
it("sign-in has exactly one code field and no settings", async () => {
  setup({ enabled: true, authenticated: false });
  await screen.findByLabelText("Access code", { exact: false });
  expect(document.querySelectorAll('input[type=password]').length).toBe(1);
  expect(screen.queryByText("Save code")).toBeNull();
});
it("first setup has new and repeat fields, no current code, rejects mismatch", async () => {
  setup({ enabled: false, authenticated: true });
  const code = await screen.findByLabelText("New code (8–128 characters)", { exact: false });
  expect(document.querySelectorAll('input[type=password]').length).toBe(2);
  expect(screen.queryByLabelText("Current code", { exact: false })).toBeNull();
  fireEvent.change(code, { target: { value: "test-code-123" } });
  fireEvent.change(screen.getByLabelText("Repeat new code", { exact: false }), { target: { value: "other-code-123" } });
  fireEvent.submit(code.closest("form"));
  expect(await screen.findByText("New codes do not match.")).toBeTruthy();
  expect(global.fetch).toHaveBeenCalledTimes(1);
});
it("protected settings have current, new and repeat; sends verified change", async () => {
  setup({ enabled: true, authenticated: true });
  const current = await screen.findByLabelText("Current code", { exact: false });
  expect(document.querySelectorAll('input[type=password]').length).toBe(3);
  fireEvent.change(current, { target: { value: "old-code-123" } });
  for (const label of ["New code (8–128 characters)", "Repeat new code"]) {
    fireEvent.change(screen.getByLabelText(label, { exact: false }), { target: { value: "new-code-123" } });
  }
  fireEvent.submit(current.closest("form"));
  await screen.findByText("Code saved. Other sessions are signed out.");
  expect(JSON.parse(global.fetch.mock.calls[1][1].body)).toEqual({ action: "save", code: "old-code-123", newCode: "new-code-123" });
});
