// @vitest-environment jsdom

import React from "react";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { VehicleReportModal } from "./vehicle-report-modal";

const listingItem = {
  id: "listing-1",
  title: "BMW X1",
  location: "Warsaw",
  url: "https://example.invalid/listing-1",
};

describe("VehicleReportModal", () => {
  afterEach(() => {
    cleanup();
    vi.restoreAllMocks();
  });

  it("renders lookup workflows and normalizes lookup submissions", async () => {
    const onLookup = vi.fn();
    const onCancelLookup = vi.fn();

    render(
      <VehicleReportModal
        state={{
          item: listingItem,
          loading: false,
          regenerating: false,
          submittingLookup: false,
          cancellingLookup: false,
          error: null,
          data: {
            status: "needs_input",
            progressMessage: "Need a date range",
            identity: { vin: "VIN123", registrationNumber: "wx 1234a" },
            lookupOptions: {
              registrationNumber: "WI 9999K",
              dateRange: { from: "2024-01-01", to: "2024-01-10" },
            },
            lookup: { registrationNumber: "ww 2222c", dateRange: { from: "2024-02-01", to: "2024-02-05" } },
          },
        }}
        redFlagState={{ item: listingItem, data: { status: "idle" }, loading: false, running: false, cancelling: false, error: null }}
        settings={{ openaiApiKeyConfigured: false }}
        onClose={vi.fn()}
        onRegenerate={vi.fn()}
        onLookup={onLookup}
        onCancelLookup={onCancelLookup}
        onStartRedFlags={vi.fn()}
        onCancelRedFlags={vi.fn()}
      />,
    );

    expect(screen.getByText("Needs input")).toBeTruthy();
    expect(screen.getByRole("button", { name: "Find red flags" })).toHaveProperty("disabled", true);

    const registrationInput = screen.getByDisplayValue("WW2222C");
    fireEvent.change(registrationInput, { target: { value: " wx 0007z " } });
    fireEvent.click(screen.getByRole("button", { name: "Search date range" }));

    expect(onLookup).toHaveBeenCalledWith({
      registrationNumber: "WX0007Z",
      dateFrom: "2024-01-01",
      dateTo: "2024-01-10",
    });

    render(
      <VehicleReportModal
        state={{
          item: listingItem,
          loading: false,
          regenerating: false,
          submittingLookup: false,
          cancellingLookup: false,
          error: null,
          data: {
            status: "running",
            progressMessage: "Searching vehicle history report...",
            identity: { vin: "VIN123", registrationNumber: "WW2222C" },
            lookupOptions: { dateRange: { from: "2024-01-01", to: "2024-01-10" } },
            lookup: { registrationNumber: "WW2222C" },
          },
        }}
        redFlagState={{ item: listingItem, data: { status: "idle" }, loading: false, running: false, cancelling: false, error: null }}
        settings={{ openaiApiKeyConfigured: false }}
        onClose={vi.fn()}
        onRegenerate={vi.fn()}
        onLookup={vi.fn()}
        onCancelLookup={onCancelLookup}
        onStartRedFlags={vi.fn()}
        onCancelRedFlags={vi.fn()}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: "Cancel lookup" }));
    expect(onCancelLookup).toHaveBeenCalled();
  });

  it("renders cached reports, analysis output, and report actions", () => {
    const onRegenerate = vi.fn();
    const onStartRedFlags = vi.fn();
    const onCancelRedFlags = vi.fn();

    render(
      <VehicleReportModal
        state={{
          item: listingItem,
          loading: false,
          regenerating: false,
          submittingLookup: false,
          cancellingLookup: false,
          error: null,
          data: {
            report: {
              api_version: "1.0.20",
              technical_data: { make: "BMW" },
              autodna_data: { unavailable: true },
              carfax_data: { risk: { stolen: false } },
              timeline_data: [{ year: 2020 }],
            },
            retrievedAt: "2026-03-24T12:00:00Z",
            identity: {
              advertId: "adv-1",
              vin: "VIN123",
              registrationNumber: "WW2222C",
              firstRegistrationDate: "2020-01-01",
            },
            summary: {
              make: "BMW",
              model: "X1",
              variant: "xDrive",
              autodnaUnavailable: true,
              carfaxAvailable: true,
            },
          },
        }}
        redFlagState={{
          item: listingItem,
          loading: false,
          running: false,
          cancelling: false,
          error: null,
          data: {
            status: "success",
            analysis: {
              summary: "Looks acceptable.",
              redFlags: ["Mileage mismatch"],
              warnings: ["Verify the seller"],
              greenFlags: ["Single owner"],
              webSearchUsed: true,
            },
          },
        }}
        settings={{ openaiApiKeyConfigured: true }}
        onClose={vi.fn()}
        onRegenerate={onRegenerate}
        onLookup={vi.fn()}
        onCancelLookup={vi.fn()}
        onStartRedFlags={onStartRedFlags}
        onCancelRedFlags={onCancelRedFlags}
      />,
    );

    expect(screen.getByText("GPT-5.4-mini reviews the listing, the detail page, and the report when it is ready.")).toBeTruthy();
    expect(screen.getByText("Looks acceptable.")).toBeTruthy();
    expect(screen.getByText("Mileage mismatch")).toBeTruthy();
    expect(screen.getByText("Used web search for VIN-related checks.")).toBeTruthy();
    expect(screen.getByText("View report")).toBeTruthy();
    expect(screen.getAllByText("Technical data").length).toBeGreaterThan(0);

    fireEvent.click(screen.getByRole("button", { name: "Regenerate report" }));
    fireEvent.click(screen.getByRole("button", { name: "Run again" }));

    expect(onRegenerate).toHaveBeenCalled();
    expect(onStartRedFlags).toHaveBeenCalled();

    cleanup();

    render(
      <VehicleReportModal
        state={{
          item: listingItem,
          loading: false,
          regenerating: false,
          submittingLookup: false,
          cancellingLookup: false,
          error: null,
          data: {
            status: "running",
            progressMessage: "Analyzing",
            identity: { vin: "VIN123" },
          },
        }}
        redFlagState={{
          item: listingItem,
          loading: false,
          running: true,
          cancelling: false,
          error: null,
          data: { status: "running", progressMessage: "Collecting data" },
        }}
        settings={{ openaiApiKeyConfigured: true }}
        onClose={vi.fn()}
        onRegenerate={vi.fn()}
        onLookup={vi.fn()}
        onCancelLookup={vi.fn()}
        onStartRedFlags={vi.fn()}
        onCancelRedFlags={onCancelRedFlags}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: "Cancel analysis" }));
    expect(onCancelRedFlags).toHaveBeenCalled();
  });
});
