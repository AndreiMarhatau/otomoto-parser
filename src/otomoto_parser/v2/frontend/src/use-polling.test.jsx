// @vitest-environment jsdom

import React from "react";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { usePolling } from "./use-polling";

function PollingHarness({ loader, enabled, reloadKey }) {
  const state = usePolling(loader, enabled, reloadKey);
  return (
    <div>
      <button type="button" onClick={() => void state.reload().catch(() => {})}>reload</button>
      <p>{state.loading ? "loading" : "loaded"}</p>
      <p>{state.error?.message || "no-error"}</p>
      <p>{state.data?.label || "no-data"}</p>
    </div>
  );
}

describe("usePolling", () => {
  afterEach(() => {
    cleanup();
    vi.restoreAllMocks();
  });

  it("polls repeatedly when enabled", async () => {
    const loader = vi
      .fn()
      .mockResolvedValueOnce({ label: "first" })
      .mockResolvedValueOnce({ label: "second" });

    render(<PollingHarness loader={loader} enabled={true} reloadKey="a" />);

    await screen.findByText("first");
    await new Promise((resolve) => window.setTimeout(resolve, 3100));
    await screen.findByText("second");
  });

  it("surfaces reload failures", async () => {
    const loader = vi
      .fn()
      .mockResolvedValueOnce({ label: "first" })
      .mockRejectedValueOnce(new Error("reload failed"));

    render(<PollingHarness loader={loader} enabled={false} reloadKey="a" />);

    await screen.findByText("first");
    fireEvent.click(screen.getByText("reload"));

    await waitFor(() => {
      expect(screen.getByText("reload failed")).toBeTruthy();
    });
  });

  it("captures initial load errors", async () => {
    const loader = vi.fn().mockRejectedValue(new Error("initial failed"));

    render(<PollingHarness loader={loader} enabled={false} reloadKey="a" />);

    await waitFor(() => {
      expect(screen.getByText("initial failed")).toBeTruthy();
    });
  });
});
