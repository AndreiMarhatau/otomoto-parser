// @vitest-environment jsdom

import React from "react";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { usePolling } from "./use-polling";
import { jsonResponse, renderSettingsPage } from "./test-helpers";

function PollingHarness({ target, enabled = false }) {
  const { data, loading, error } = usePolling(() => Promise.resolve({ item: { label: target } }), enabled, target);

  if (loading && !data) {
    return <p>Loading {target}</p>;
  }
  if (error) {
    return <p>{error.message}</p>;
  }
  return <p>{data?.item?.label}</p>;
}

describe("SettingsPage polling regression", () => {
  afterEach(() => {
    cleanup();
    vi.restoreAllMocks();
  });

  it("does not re-fetch /api/settings in a tight loop when polling is disabled", async () => {
    const fetchMock = vi.fn(async (path) => {
      if (path === "/api/settings") {
        return jsonResponse({
          item: {
            openaiApiKeyConfigured: false,
            openaiApiKeySource: null,
            openaiApiKeyMasked: null,
            openaiApiKeyStored: false,
          },
        });
      }
      throw new Error(`Unhandled fetch path: ${path}`);
    });
    global.fetch = fetchMock;

    renderSettingsPage();

    expect(await screen.findByText("Configured")).toBeTruthy();
    expect(screen.getByText("Red-flag analysis uses GPT-5.4 with web search. Stored keys override `OPENAI_API_KEY` from the server environment.")).toBeTruthy();

    const initialSettingsCalls = fetchMock.mock.calls.filter(([path]) => path === "/api/settings").length;
    expect(initialSettingsCalls).toBeLessThanOrEqual(2);

    await new Promise((resolve) => {
      window.setTimeout(resolve, 100);
    });

    const finalSettingsCalls = fetchMock.mock.calls.filter(([path]) => path === "/api/settings").length;
    expect(finalSettingsCalls).toBe(initialSettingsCalls);
  });

  it("re-fetches immediately when the reload key changes while polling is disabled", async () => {
    const { rerender } = render(<PollingHarness target="alpha" enabled={false} />);

    expect(await screen.findByText("alpha")).toBeTruthy();

    rerender(<PollingHarness target="beta" enabled={false} />);

    expect(await screen.findByText("beta")).toBeTruthy();
  });

  it("saves and clears the configured API key", async () => {
    const fetchMock = vi.fn(async (path, options = {}) => {
      if (path === "/api/settings" && (!options.method || options.method === "GET")) {
        return jsonResponse({
          item: {
            openaiApiKeyConfigured: true,
            openaiApiKeySource: "stored",
            openaiApiKeyMasked: "sk-***",
            openaiApiKeyStored: true,
          },
        });
      }
      if (path === "/api/settings" && options.method === "PUT") {
        return jsonResponse({ ok: true });
      }
      throw new Error(`Unhandled fetch path: ${path}`);
    });
    global.fetch = fetchMock;

    renderSettingsPage();

    const input = await screen.findByPlaceholderText("sk-...");
    fireEvent.change(input, { target: { value: "sk-test" } });
    fireEvent.click(screen.getByRole("button", { name: "Save key" }));
    fireEvent.click(await screen.findByRole("button", { name: "Clear stored key" }));

    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledWith(
        "/api/settings",
        expect.objectContaining({ method: "PUT" }),
      );
    });
  });
});
