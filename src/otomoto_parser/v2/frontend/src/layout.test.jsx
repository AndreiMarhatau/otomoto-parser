// @vitest-environment jsdom

import React from "react";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import { Breadcrumbs, IconButton, Metric, Shell, StatusPill, buildPageItems, scrollWindowToPosition } from "./layout";

describe("layout helpers", () => {
  afterEach(() => {
    cleanup();
    vi.restoreAllMocks();
  });

  it("scrolls the window and document roots", () => {
    window.scrollTo = vi.fn();
    document.documentElement.scrollTop = 0;
    document.body.scrollTop = 0;

    scrollWindowToPosition(120);

    expect(window.scrollTo).toHaveBeenCalledWith(0, 120);
    expect(document.documentElement.scrollTop).toBe(120);
    expect(document.body.scrollTop).toBe(120);
  });

  it("builds compact and ellipsis pagination ranges", () => {
    expect(buildPageItems(2, 5)).toEqual([1, 2, 3, 4, 5]);
    expect(buildPageItems(5, 10)).toEqual([1, "ellipsis", 4, 5, 6, "ellipsis", 10]);
  });

  it("renders button and link icon buttons plus layout wrappers", () => {
    const onClick = vi.fn();
    render(
      <MemoryRouter>
        <Shell title="Dashboard">
          <Breadcrumbs items={[{ label: "Requests", to: "/" }, { label: "Details" }]} />
          <IconButton title="Refresh" onClick={onClick}>
            <span>R</span>
          </IconButton>
          <IconButton title="Docs" href="https://example.invalid/docs">
            <span>D</span>
          </IconButton>
          <StatusPill status="ready" />
          <Metric label="Pages" value={null} />
        </Shell>
      </MemoryRouter>,
    );

    fireEvent.click(screen.getByRole("button", { name: "Refresh" }));
    expect(onClick).toHaveBeenCalled();
    expect(screen.getByRole("link", { name: "Docs" }).getAttribute("href")).toBe("https://example.invalid/docs");
    expect(screen.getByText("Dashboard")).toBeTruthy();
    expect(screen.getByText("Requests")).toBeTruthy();
    expect(screen.getByText("ready")).toBeTruthy();
    expect(screen.getByText("Pages")).toBeTruthy();
    expect(screen.getByText("—")).toBeTruthy();
  });
});
