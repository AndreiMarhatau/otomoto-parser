// @vitest-environment jsdom

import React from "react";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { ListingCard } from "./listing-card";

describe("ListingCard", () => {
  afterEach(() => {
    cleanup();
    vi.restoreAllMocks();
  });

  it("renders listing details and success report state", () => {
    const onOpenLocation = vi.fn();
    const onOpenReport = vi.fn();

    render(
      <ListingCard
        item={{
          id: "listing-1",
          title: "BMW X1",
          imageUrl: "https://example.invalid/image.jpg",
          url: "https://example.invalid/listing-1",
          price: 10000,
          priceCurrency: "PLN",
          shortDescription: "Example",
          location: "Warsaw",
          createdAt: "2026-03-24T12:00:00Z",
          category: "Price evaluation out of range",
          dataVerified: true,
          vehicleReport: { status: "success", retrievedAt: "2026-03-24T12:00:00Z" },
        }}
        assignableCategories={[]}
        categoryBusy={false}
        onAssignCategories={vi.fn()}
        onCreateCategory={vi.fn()}
        onOpenLocation={onOpenLocation}
        onOpenReport={onOpenReport}
        distanceLabel="5 km away"
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: "Warsaw" }));
    fireEvent.click(screen.getByRole("button", { name: "Vehicle report" }));

    expect(onOpenLocation).toHaveBeenCalledWith({ title: "BMW X1", location: "Warsaw" });
    expect(onOpenReport).toHaveBeenCalled();
    expect(screen.getByText("Verified data")).toBeTruthy();
    expect(screen.getByText("5 km away")).toBeTruthy();
  });

  it("renders fallback states and failed report metadata", () => {
    render(
      <ListingCard
        item={{
          id: "listing-2",
          title: "Audi A4",
          url: "https://example.invalid/listing-2",
          price: null,
          priceCurrency: "PLN",
          shortDescription: "",
          location: "",
          createdAt: "",
          vehicleReport: { status: "failed", lastAttemptAt: "2026-03-24T12:00:00Z" },
        }}
        assignableCategories={[]}
        categoryBusy={true}
        onAssignCategories={vi.fn()}
        onCreateCategory={vi.fn()}
        onOpenLocation={vi.fn()}
        onOpenReport={vi.fn()}
        distanceLabel="No location"
      />,
    );

    expect(screen.getByText("No short description.")).toBeTruthy();
    expect(screen.getAllByText("No location")).toHaveLength(2);
    expect(screen.getByText("No price evaluation")).toBeTruthy();
    expect(screen.getByText("No engine capacity")).toBeTruthy();
  });
});
