// @vitest-environment jsdom

import React from "react";
import { render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { AppThemeProvider, buildTheme, themeTokens } from "./app-theme";
import { IconDownload, IconRefresh } from "./icons";

describe("AppThemeProvider", () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("renders children in light mode and exposes icon exports", async () => {
    const mediaQueryMock = vi.fn((query) => ({
      matches: false,
      media: query,
      onchange: null,
      addListener: vi.fn(),
      removeListener: vi.fn(),
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
      dispatchEvent: vi.fn(),
    }));
    Object.defineProperty(window, "matchMedia", { writable: true, value: mediaQueryMock });

    render(
      <AppThemeProvider>
        <div>theme child</div>
        <IconRefresh data-testid="refresh-icon" />
        <IconDownload data-testid="download-icon" />
      </AppThemeProvider>,
    );

    expect(screen.getByText("theme child")).toBeTruthy();
    expect(screen.getByTestId("refresh-icon")).toBeTruthy();
    expect(screen.getByTestId("download-icon")).toBeTruthy();
    expect(mediaQueryMock).toHaveBeenCalled();
  });

  it("renders children in dark mode", () => {
    Object.defineProperty(window, "matchMedia", {
      writable: true,
      value: vi.fn((query) => ({
      matches: query.includes("dark"),
      media: query,
      onchange: null,
      addListener: vi.fn(),
      removeListener: vi.fn(),
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
      dispatchEvent: vi.fn(),
      })),
    });

    render(
      <AppThemeProvider>
        <div>dark child</div>
      </AppThemeProvider>,
    );

    expect(screen.getByText("dark child")).toBeTruthy();
  });

  it("uses the exported token map as the single theme source of truth", () => {
    const lightTheme = buildTheme("light");
    const darkTheme = buildTheme("dark");

    expect(lightTheme.customTokens).toEqual(themeTokens.light);
    expect(darkTheme.customTokens).toEqual(themeTokens.dark);
    expect(lightTheme.palette.primary.main).toBe(themeTokens.light.palette.primary);
    expect(darkTheme.palette.background.default).toBe(themeTokens.dark.palette.backgroundDefault);
    expect(lightTheme.components.MuiOutlinedInput.styleOverrides.root({ theme: lightTheme }).backgroundColor).toBe(themeTokens.light.surfaces.field);
    expect(darkTheme.components.MuiOutlinedInput.styleOverrides.root({ theme: darkTheme }).backgroundColor).toBe(themeTokens.dark.surfaces.field);
    expect(lightTheme.components.MuiChip.styleOverrides.root({ theme: lightTheme }).backgroundColor).toContain("rgba");
    expect(lightTheme.components.MuiDialog.styleOverrides.paper({ theme: lightTheme }).border).toContain(lightTheme.palette.divider);
    expect(darkTheme.components.MuiAccordion.styleOverrides.root({ theme: darkTheme }).border).toContain(darkTheme.palette.divider);
    expect(darkTheme.customTokens.gradients.body).toContain("radial-gradient");
  });
});
