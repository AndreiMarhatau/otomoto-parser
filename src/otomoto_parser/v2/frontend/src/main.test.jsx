// @vitest-environment jsdom

import React from "react";
import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

describe("main entrypoint", () => {
  afterEach(() => {
    cleanup();
    vi.restoreAllMocks();
    vi.resetModules();
    document.body.innerHTML = "";
  });

  it("exports App and boots React when a root element exists", async () => {
    document.body.innerHTML = '<div id="root"></div>';
    const renderMock = vi.fn();
    const createRootMock = vi.fn(() => ({ render: renderMock }));

    vi.doMock("react-dom/client", () => ({
      default: { createRoot: createRootMock },
      createRoot: createRootMock,
    }));

    const module = await import("./main.jsx");

    expect(typeof module.App).toBe("function");
    expect(createRootMock).toHaveBeenCalled();
    expect(renderMock).toHaveBeenCalled();
  });

  it("renders the exported app routes", async () => {
    document.body.innerHTML = '<div id="app-test-root"></div>';
    const { App } = await import("./main.jsx");

    window.history.pushState({}, "", "/settings");
    render(<App />);

    expect(screen.getByRole("heading", { name: "Settings" })).toBeTruthy();
  });
});
